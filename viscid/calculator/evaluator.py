#!/usr/bin/env python
"""Used for evaluating equations given to a script from the user

This tries very feebly to limit the namespace available to
the equation which is done using eval. As a result, this
functionality should NOT be used on untrusted input. To make
this super clear, the user MUST enable this functionality on
a per-script basis, or by setting calculator.evaluator.enabled: true
in their viscidrc.
"""

from __future__ import print_function, division
import re

import numpy as np
try:
    import numexpr as ne
    _has_numexpr = True
except ImportError:
    _has_numexpr = False

from viscid import logger
from viscid import field
from viscid.calculator import calc

enabled = False


def evaluate(grid, result_name, eqn, try_numexpr=True):
    """Evaluate an equation on a grid

    Examples:
        To use this function directly

            >>> evaluator.enabled = True
            >>> f = viscid.load_file("...")
            >>> evaluator.evaluate(f.get_grid(),
                                   "sqrt(vx**2+vy**2+vz**2)",
                                   "speed")
            <viscid.field.ScalarField object at ...>

        Or, for short, you can as a grid to evaluate implicitly,

            >> evaluator.enabled = True
            >> f = viscid.load_file("...")
            >> speed = f["speed=sqrt(vx**2+vy**2+vz**2)"]
            <viscid.field.ScalarField object at ...>

    Parameters:
        grid: a grid instance where the fields live
        result_name (str): Used for the name and pretty_name of the
            resulting field
        eqn (str): the equation, if a symbol exists in the numpy
            namespace, then that's how it is interpreted, otherwise,
            the symbol will be looked up in the grid

    Returns:
        Field instance
    """
    if not enabled:
        raise RuntimeError("You must enable the evaluator with "
                           "`viscid.calculator.evaluator.enabled = True`, "
                           "or in your viscidrc.")

    if try_numexpr:
        try:
            return _evaluate_numexpr(grid, result_name, eqn)
        except RuntimeError:
            pass
        except TypeError:
            logger.warn("Numexpr couldn't understand a math function you "
                        "tried to use in '{0}', falling back to numpy"
                        "".format(eqn))
    return _evaluate_numpy(grid, result_name, eqn)

def _evaluate_numexpr(grid, result_name, eqn):
    """
    Returns:
        Field

    Raises:
        RuntimeError, if no numexpr, or if evaluate is not enabled
        TypeError, if numexpr couldn't understand a math input
    """
    if not _has_numexpr:
        raise RuntimeError("Evaluate not enabled, or numexpr not installed.")

    # salt symbols that don't look like math functions and look them up
    # in the grid
    salt = "_"
    _symbol_re = r"\b([_A-Za-z][_a-zA-Z0-9]*)\b"
    var_re = _symbol_re + r"(?!\s*\()"
    flds = []
    local_dict = dict()

    def var_salter(symbols):
        symbol = symbols.groups()[0]
        salted_symbol = salt + symbol
        # yes, i'm not using dict.update on purpose since grid's
        # getitem might copy the array
        if not salted_symbol in local_dict:
            flds.append(grid[symbol])
            local_dict[salted_symbol] = flds[-1].data
        return salted_symbol

    salted_eqn = re.sub(var_re, var_salter, eqn)

    arr = ne.evaluate(salted_eqn, local_dict=local_dict, global_dict=None)

    # FIXME: actually detect the type of field instead of asserting it's
    # a scalar... also maybe auto-detect reduction operations?
    if len(flds) > 0:
        ctx = dict(name=result_name, pretty_name=result_name)
        return flds[0].wrap(arr, context=ctx)
    else:
        return field.wrap_field("Scalar", result_name, grid.crds, arr)

def _evaluate_numpy(grid, result_name, eqn):
    """
    Returns:
        Field
    """
    if not enabled:
        raise RuntimeError("Evaluate is not enabled")

    # salt variable names
    salt = "_"
    _symbol_re = r"(['\"]?\b[_A-Za-z][_a-zA-Z0-9]*)\b"
    var_re = _symbol_re + r"(?!\s*\()"
    local_dict = dict()

    def var_salter(symbols):
        symbol = symbols.groups()[0]
        if symbol.startswith("'"):
            return symbol
        salted_symbol = salt + symbol
        # yes, i'm not using dict.update on purpose since grid's
        # getitem might copy the array
        if not salted_symbol in local_dict:
            local_dict[salted_symbol] = grid[symbol]
        return salted_symbol
    salted_eqn = re.sub(var_re, var_salter, eqn)

    # salt function names
    func_re = _symbol_re + r"(\s*\()"
    def func_salter(symbols):
        symbol = symbols.groups()[0]
        salted_symbol = salt + symbol
        if salted_symbol not in local_dict:
            if hasattr(calc, symbol):
                local_dict[salted_symbol] = getattr(calc, symbol)
            elif hasattr(np, symbol):
                local_dict[salted_symbol] = getattr(np, symbol)
        return salted_symbol + "("
    salted_eqn = re.sub(func_re, func_salter, salted_eqn)

    # run eval
    fld = eval(salted_eqn, {}, local_dict)
    try:
        fld.name = result_name
        fld.pretty_name = result_name
    except AttributeError:
        pass
    return fld


if __name__ == "__main__":
    import os
    from matplotlib import pyplot as plt
    import viscid
    from viscid.plot import mpl
    enabled = True
    _d = os.path.dirname(viscid.__file__)
    _g = viscid.load_file(_d + "/../sample/sample.py_0.xdmf").get_grid()
    plt.subplot(211)
    _fld = evaluate(_g, "speed", "sqrt(vx**2 + vy**2 + sqrt(vz**4))")
    mpl.plot(_fld, show=False)
    plt.subplot(212)
    _fld = evaluate(_g, "speed", "sqrt(vx**2 + vy**2 + sqrt(vz**4))",
                    try_numexpr=False)
    mpl.plot(_fld, show=True)

##
## EOF
##
