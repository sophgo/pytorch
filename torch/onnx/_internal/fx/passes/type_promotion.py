# Owner(s): ["module: onnx"]
from __future__ import annotations

import dataclasses
import inspect
import logging
from types import ModuleType

from typing import Any, Callable, Mapping, Optional, Sequence, Set, Union

import sympy

import torch
import torch._ops
import torch.fx
import torch.fx.traceback as fx_traceback

from torch import _prims_common, _refs

from torch._prims_common import (
    ELEMENTWISE_TYPE_PROMOTION_KIND,
    wrappers as _prims_common_wrappers,
)
from torch._refs import linalg as _linalg_refs, nn as _nn_refs, special as _special_refs
from torch._refs.nn import functional as _functional_refs
from torch._subclasses import fake_tensor
from torch.fx.experimental import proxy_tensor

# Imported to resolve beartype issue when type checking node.Argument.
from torch.fx.node import Node  # noqa: F401
from torch.onnx._internal import _beartype
from torch.onnx._internal.fx import _pass, diagnostics
from torch.utils import _python_dispatch, _pytree

logger = logging.getLogger(__name__)

# Expected argument type inferred from _prims_common.elementwise_dtypes
TorchArg = Union[
    _prims_common.TensorLike,
    bool,
    int,
    float,
    complex,
    torch.SymInt,
    torch.SymFloat,
    sympy.Symbol,
]

# TODO: move to type utils.
_SCALAR_TYPE_TENSOR_DTYPE_MAP: Mapping[type, torch.dtype] = {
    bool: torch.bool,
    int: torch.int64,
    float: torch.float32,
    complex: torch.complex32,
}


def _try_getclosurevars(func):
    try:
        return inspect.getclosurevars(func)
    except TypeError as e:
        return None


@_beartype.beartype
def _get_fake_tensor_val(node: torch.fx.Node) -> fake_tensor.FakeTensor:
    val = node.meta.get("val", None)
    if not isinstance(val, fake_tensor.FakeTensor):
        raise RuntimeError(
            f"Cannot retrieve fake tensor from node {node}. Got type({type(val)}) instead."
        )
    return val


class TypePromotionRule:
    """Defines how to perform type promotion for 'torch.ops.{namespace}.{op_name}'."""

    def __init__(
        self,
        namespace: str,
        op_name: str,
        promote_args_positions: Sequence[int],
        promote_kwargs_names: Sequence[str],
        promotion_kind: _prims_common.ELEMENTWISE_TYPE_PROMOTION_KIND,
    ):
        self.namespace = namespace
        self.op_name = op_name
        self.promote_args_positions = promote_args_positions
        self.promote_kwargs_names = promote_kwargs_names
        self.promotion_kind = promotion_kind

    def __hash__(self) -> int:
        return f"{self.namespace}.{self.op_name}".__hash__()

    def __repr__(self):
        return (
            f"TypePromotionRule('{self.namespace}', '{self.op_name}', {self.promote_args_positions}, "
            f"{self.promote_kwargs_names}, {self.promotion_kind})"
        )

    def __eq__(self, __value: object) -> bool:
        if not isinstance(__value, TypePromotionRule):
            return False
        return (
            self.namespace == __value.namespace
            and self.op_name == __value.op_name
            and self.promote_args_positions == __value.promote_args_positions
            and self.promote_kwargs_names == __value.promote_kwargs_names
            and self.promotion_kind == __value.promotion_kind
        )

    def is_valid(self) -> bool:
        """Check if the rule is valid."""
        # This always returns a module. If the module does not exist it will be created.
        module = getattr(torch.ops, self.namespace)
        py_op = getattr(module, self.op_name, None)
        if py_op is None:
            logger.warning(
                "Cannot find op: %s in module: %s", self.op_name, self.namespace
            )
            return False
        if not isinstance(py_op, torch._ops.OpOverloadPacket):
            logger.warning(
                "Op: torch.ops.%s.%s is not an OpOverloadPacket, got: %s",
                self.namespace,
                self.op_name,
                type(py_op),
            )
            return False

        return True

    def preview_type_promotion(
        self, args: tuple, kwargs: dict
    ) -> TypePromotionSnapshot:
        """Preview type promotion results for the given fx node.

        Returns a TypePromotionSnapshot object that contains the promoted dtypes for
        the arguments and the expected output dtype of the given fx node.
        """

        candidate_args = {
            i: args[i]
            for i in self.promote_args_positions
            if i < len(args) and args[i] is not None
        }
        candidate_kwargs = {
            name: kwargs[name]
            for name in self.promote_kwargs_names
            if name in kwargs and kwargs[name] is not None
        }

        computed_dtype, result_dtype = _prims_common.elementwise_dtypes(
            *_pytree.tree_flatten(candidate_args)[0],
            *_pytree.tree_flatten(candidate_kwargs)[0],
            type_promotion_kind=self.promotion_kind,
        )

        return TypePromotionSnapshot(
            {i: computed_dtype for i in candidate_args.keys()},
            {name: computed_dtype for name in candidate_kwargs.keys()},
            result_dtype,
        )


# NOTE: BELOW TABLE IS GENERATED FROM `TypePromotionRuleSetGenerator.generate_from_torch_refs`.
# DO NOT EDIT MANUALLY !!!
# For missing rules or discrepancies, please
# 1. Run `pytest test/onnx/test_fx_type_promotion.py` to validate if the generated rule set is current.
#    If it is not, update with new generated set.
# 2. If discrepancy still exists, consider debugging torch._refs or report a bug.
# 3. If rule is still missing, add them to `_EXTRA_TYPE_PROMOTION_RULE_SET` or report a bug.
_GENERATED_ATEN_TYPE_PROMOTION_RULE_SET = {
    TypePromotionRule(
        "aten", "abs", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.COMPLEX_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "abs_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.COMPLEX_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "acos", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "acos_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "acosh", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "acosh_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "add", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "add_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "addcdiv", [0, 1, 2], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "addcdiv_", [0, 1, 2], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "addcmul", [0, 1, 2], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "addcmul_", [0, 1, 2], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "addr", [0, 1, 2], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "asin", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "asin_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "asinh", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "asinh_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "atan", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "atan2", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "atan2_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "atan_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "atanh", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "atanh_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "bitwise_and", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "bitwise_and_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten",
        "bitwise_left_shift",
        [0, 1],
        [],
        ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT,
    ),
    TypePromotionRule(
        "aten",
        "bitwise_left_shift_",
        [0, 1],
        [],
        ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT,
    ),
    TypePromotionRule(
        "aten", "bitwise_not", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "bitwise_not_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "bitwise_or", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "bitwise_or_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten",
        "bitwise_right_shift",
        [0, 1],
        [],
        ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT,
    ),
    TypePromotionRule(
        "aten",
        "bitwise_right_shift_",
        [0, 1],
        [],
        ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT,
    ),
    TypePromotionRule(
        "aten", "bitwise_xor", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "bitwise_xor_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "cat", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.NO_OPMATH
    ),
    TypePromotionRule(
        "aten", "cauchy", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "cauchy_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule("aten", "ceil", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule(
        "aten", "ceil_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule("aten", "celu", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule(
        "aten", "celu_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "clamp", [0, 1, 2], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "clamp_", [0, 1, 2], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "copysign", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "copysign_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "cos", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "cos_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "cosh", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "cosh_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "deg2rad", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "deg2rad_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "digamma", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "digamma_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule("aten", "elu", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule("aten", "elu_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule(
        "aten", "eq", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "eq_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "erf", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "erf_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "erfc", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "erfc_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "erfinv", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "erfinv_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "exp", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "exp2", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "exp2_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "exp_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "expm1", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "expm1_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "exponential", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "exponential_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "fill", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.NO_OPMATH
    ),
    TypePromotionRule(
        "aten", "floor", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "floor_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "floor_divide", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "floor_divide_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "fmax", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "fmin", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "fmod", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "fmod_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule("aten", "frac", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule(
        "aten", "frac_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "gcd", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "gcd_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "ge", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "ge_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule("aten", "gelu", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule(
        "aten", "geometric", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "geometric_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule("aten", "glu", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule(
        "aten", "gt", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "gt_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "hardtanh", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "heaviside", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "heaviside_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "huber_loss", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "hypot", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "hypot_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "i0", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "i0_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "igamma", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "igamma_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "igammac", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "igammac_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "isfinite", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "isinf", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "isnan", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "isneginf", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "isposinf", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "isreal", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "l1_loss", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.COMPLEX_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "lcm", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "lcm_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "le", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "le_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "leaky_relu", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "lerp", [0, 1, 2], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "lerp_", [0, 1, 2], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "lgamma", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "lgamma_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "log", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "log10", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "log10_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "log1p", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "log1p_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "log2", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "log2_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "log_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "log_normal", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "log_normal_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "logaddexp", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "logaddexp2", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "logical_and", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "logical_and_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "logical_not", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "logical_not_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "logical_or", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "logical_or_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "logical_xor", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "logical_xor_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "logit", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "logsumexp", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "lt", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "lt_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "maximum", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "minimum", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule("aten", "mish", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule(
        "aten", "mish_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "mse_loss", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.COMPLEX_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "mul", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "mul_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "ne", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "ne_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule("aten", "neg", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule("aten", "neg_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule(
        "aten", "nextafter", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.NO_OPMATH
    ),
    TypePromotionRule(
        "aten", "nextafter_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.NO_OPMATH
    ),
    TypePromotionRule(
        "aten", "nll_loss", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "normal", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "normal_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "pdist", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten",
        "poisson_nll_loss",
        [0, 1],
        [],
        ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT,
    ),
    TypePromotionRule(
        "aten", "pow", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.BOOL_TO_LONG
    ),
    TypePromotionRule(
        "aten", "pow_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.BOOL_TO_LONG
    ),
    TypePromotionRule(
        "aten", "prelu", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "rad2deg", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "rad2deg_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "reciprocal", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "reciprocal_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule("aten", "relu", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule(
        "aten", "remainder", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "remainder_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "round", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "rsqrt", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "rsqrt_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule("aten", "selu", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule(
        "aten", "selu_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule("aten", "sgn", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule("aten", "sgn_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule(
        "aten", "sigmoid", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "sigmoid_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule("aten", "sign", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT),
    TypePromotionRule(
        "aten", "sign_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "signbit", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.ALWAYS_BOOL
    ),
    TypePromotionRule(
        "aten", "sin", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "sin_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "sinc", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "sinc_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "sinh", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "sinh_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten",
        "smooth_l1_loss",
        [0, 1],
        [],
        ELEMENTWISE_TYPE_PROMOTION_KIND.COMPLEX_TO_FLOAT,
    ),
    TypePromotionRule(
        "aten", "softplus", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "sqrt", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "sqrt_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "square", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.BOOL_TO_LONG
    ),
    TypePromotionRule(
        "aten", "square_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.BOOL_TO_LONG
    ),
    TypePromotionRule(
        "aten", "sub", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "sub_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "tan", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "tan_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "tanh", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "tanh_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "threshold", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "threshold_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "true_divide", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "true_divide_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "trunc", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "trunc_", [0], [], ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT
    ),
    TypePromotionRule(
        "aten", "where", [1, 2], [], ELEMENTWISE_TYPE_PROMOTION_KIND.NO_OPMATH
    ),
    TypePromotionRule(
        "aten", "xlogy", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
    TypePromotionRule(
        "aten", "xlogy_", [0, 1], [], ELEMENTWISE_TYPE_PROMOTION_KIND.INT_TO_FLOAT
    ),
}

# Manually curated extra type promotion rules.
_EXTRA_TYPE_PROMOTION_RULE_SET = {
    # torch._refs skips type promotion annotations for `clamp_min` and `clamp_max` since
    # the call is routed to `aten.clamp`, which is annotated with type promotion rules.
    TypePromotionRule(
        "aten",
        "clamp_min",
        promote_args_positions=(0, 1),
        promote_kwargs_names=(),
        promotion_kind=_prims_common.ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT,
    ),
    TypePromotionRule(
        "aten",
        "clamp_max",
        promote_args_positions=(0, 1),
        promote_kwargs_names=(),
        promotion_kind=_prims_common.ELEMENTWISE_TYPE_PROMOTION_KIND.DEFAULT,
    ),
    # TODO: torch.ops.aten.div.Tensor_mode applies different type promotion rules
    # depending on the value of the `mode` argument.
}


class TypePromotionRuleSetGenerator:
    """Hackly distilling info from reference ops decorated with type promotion rule."""

    @classmethod
    def generate_from_torch_refs(cls) -> Set[TypePromotionRule]:
        """Parse type promotion rules from reference ops under torch._C._refs."""
        table = set()
        table.update(cls._parse_torch_refs(_refs))
        table.update(cls._parse_torch_refs(_nn_refs))
        table.update(cls._parse_torch_refs(_linalg_refs))
        table.update(cls._parse_torch_refs(_special_refs))
        table.update(cls._parse_torch_refs(_functional_refs))
        return table

    @classmethod
    def _parse_torch_refs(cls, ref_module: ModuleType) -> Set[TypePromotionRule]:
        logger.info("Processing module: %s", ref_module.__name__)
        table = set()
        for name in ref_module.__all__:
            decorated_op = getattr(ref_module, name)
            rule = cls._parse_type_promotion_rule_from_refs_op(decorated_op)
            if rule is not None and rule.is_valid():
                table.add(rule)

        return table

    @classmethod
    def _parse_type_promotion_rule_from_refs_op(
        cls,
        decorated_op: Callable,
    ) -> Optional[TypePromotionRule]:
        """Retrieve and parse type promotion decorator from op under torch._refs."""
        fn = decorated_op
        type_promo_wrapper = None
        while fn_closure_vars := _try_getclosurevars(fn):
            if "fn" not in fn_closure_vars.nonlocals:
                break
            if "self" in fn_closure_vars.nonlocals and isinstance(
                fn_closure_vars.nonlocals["self"],
                _prims_common_wrappers.elementwise_type_promotion_wrapper,
            ):
                type_promo_wrapper = fn_closure_vars.nonlocals["self"]
                break
            fn = fn_closure_vars.nonlocals["fn"]

        if type_promo_wrapper is not None:
            signature = inspect.signature(decorated_op)

            pos = 0
            promote_args_positions = []
            promote_kwargs_names = []

            if type_promo_wrapper.type_promoting_arg_names is not None:
                for name, param in signature.parameters.items():
                    if name in type_promo_wrapper.type_promoting_arg_names:
                        if param.kind in (
                            param.POSITIONAL_OR_KEYWORD,
                            param.POSITIONAL_ONLY,
                        ):
                            promote_args_positions.append(pos)
                        elif param.kind == param.KEYWORD_ONLY:
                            promote_kwargs_names.append(name)
                    pos += 1

            return TypePromotionRule(
                "aten",
                decorated_op.__name__,
                promote_args_positions=promote_args_positions,
                promote_kwargs_names=promote_kwargs_names,
                promotion_kind=type_promo_wrapper.type_promotion_kind,
            )

        logger.warning(
            "Cannot find type promotion rule for: %s.%s",
            decorated_op.__module__,
            decorated_op.__name__,
        )
        return None


class TypePromotionTable:
    """Type promotion table for torch.ops."""

    def __init__(self):
        self._rule_table = {}
        for rule in _GENERATED_ATEN_TYPE_PROMOTION_RULE_SET:
            self.add_rule(rule)
        for rule in _EXTRA_TYPE_PROMOTION_RULE_SET:
            self.add_rule(rule)

    def add_rule(self, rule: TypePromotionRule):
        """Add a type promotion rule for a python op in a torch.ops module.

        Args:
            rule: Type promotion rule.
            module: Module containing the op. E.g. torch.ops.aten.

        Raises:
            ValueError: If the rule is invalid.
        """
        if not rule.is_valid():
            raise ValueError("Invalid type promotion rule: {}".format(rule))
        self._rule_table[f"{rule.namespace}.{rule.op_name}"] = rule

    def get_rule(
        self, py_op: torch._ops.OpOverloadPacket
    ) -> Optional[TypePromotionRule]:
        """Get type promotion rule for a python op under 'torch.ops.<namespace>'."""
        return self._rule_table.get(str(py_op), None)


@dataclasses.dataclass
class TypePromotionSnapshot:
    """Type promotion snapshot for a node in a graph.

    Contains info about the dtype to promote to for args and kwargs that needs promoting.
    Contains the expected output dtype of the node.
    """

    args_dtypes: Mapping[int, torch.dtype]
    """Mapping from arg position to dtype to promote to."""

    kwargs_dtypes: Mapping[str, torch.dtype]
    """Mapping from kwarg name to dtype to promote to."""

    out_dtype: torch.dtype
    """Expected output dtype of the node."""


@_beartype.beartype
def get_type_promotion_rule(
    diagnostic: diagnostics.Diagnostic,
    node: torch.fx.Node,
    type_promotion_table: TypePromotionTable,
) -> Optional[TypePromotionRule]:
    """Get type promotion rule for a node.

    Args:
        diagnostic: Diagnostic object.
        node: Node to get type promotion rule for.
        type_promotion_table: Type promotion table.

    Returns:
        Type promotion rule for the node.
    """
    op = node.target
    if not isinstance(op, torch._ops.OpOverload):
        # TODO(bowbao): diagnostic.emit api.
        diagnostic.with_additional_message(
            f"Skipped. node.target is not OpOverload. Got type: {type(op)}"
        )
        return None
    if (rule := type_promotion_table.get_rule(op.overloadpacket)) is None:
        diagnostic.with_additional_message(
            f"Skipped. Cannot find type promotion rule for op: {op}"
        )
        return None

    diagnostic.with_additional_message(f"Found type promotion rule: {rule}")
    return rule


class _OpTraceDispatchMode(_python_dispatch.TorchDispatchMode):
    """Trace ops that were dispatched."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.traced_ops = []

    def __torch_dispatch__(self, func, types, args=(), kwargs=None):
        self.traced_ops.append(func)
        return func(*args, **kwargs)


@_beartype.beartype
def find_compatible_op_overload(
    node: torch.fx.Node, args: tuple, kwargs: dict
) -> torch._ops.OpOverload:
    """Find the compatible op overload for a node with a given set of args and kwargs.

    Returns:
        Compatible op overload for the node.

    Raises:
        RuntimeError: If no compatible op overload is found.
        AssertionError: If compatible op overload is not an instance of torch._ops.OpOverload.
        AssertionError: If op is being decomposed.
    """
    target = node.target
    assert isinstance(
        target, torch._ops.OpOverload
    ), f"Expected OpOverload, got {type(target)}"
    op = target.overloadpacket
    op_trace_dispatch_mode = _OpTraceDispatchMode()
    with op_trace_dispatch_mode:
        op(*args, **kwargs)
    assert (
        len(op_trace_dispatch_mode.traced_ops) == 1
    ), f"Expected 1 traced op, got {len(op_trace_dispatch_mode.traced_ops)}"

    new_op_overload = op_trace_dispatch_mode.traced_ops[0]
    assert isinstance(
        new_op_overload, torch._ops.OpOverload
    ), f"Expected OpOverload, got {type(new_op_overload)}"

    return new_op_overload


@dataclasses.dataclass
class NodeMeta:
    """Required meta data for fx.Node during onnx export.

    For each field, it directly maps to `fx.Node.meta` via `meta[field.name] = field.value`.
    """

    stack_trace: str
    nn_module_stack: Any

    def assign_to_node(self, node: torch.fx.Node) -> None:
        """Assigns the meta data to the given node by updating `node.meta`."""
        for field in dataclasses.fields(self):
            setattr(node.meta, field.name, getattr(self, field.name))


class ExplicitTypePromotionPass(_pass.Transform, torch.fx.Interpreter):
    def __init__(
        self,
        diagnostic_context,
        module: torch.fx.GraphModule,
        type_promotion_table: Optional[TypePromotionTable] = None,
    ):
        super().__init__(diagnostic_context, module)
        torch.fx.Interpreter.__init__(self, module)
        self.type_promotion_table = type_promotion_table or TypePromotionTable()

    def _run_node_and_update_meta_val(self, node) -> Any:
        out = super().run_node(node)
        self.env[node] = out
        node.meta["val"] = proxy_tensor.extract_val(out)
        return out

    @_beartype.beartype
    def _create_node(
        self,
        graph: torch.fx.Graph,
        op_type: str,
        target: torch.fx.node.Target,
        args: tuple,
        kwargs: dict,
        node_meta: Optional[NodeMeta] = None,
    ) -> torch.fx.Node:
        assert op_type in (
            "call_function",
            "call_method",
            "get_attr",
            "call_module",
            "placeholder",
            "output",
        ), f"Unexpected op_type: {op_type}"
        node = getattr(graph, op_type)(target, args, kwargs)
        self._run_node_and_update_meta_val(node)
        if node_meta is not None:
            node_meta.assign_to_node(node)
        else:
            node.meta.update(
                (k, v)
                for k, v in fx_traceback.get_current_meta().items()
                if k not in node.meta
            )
        return node

    @_beartype.beartype
    def _explicit_type_promote_arg(
        self,
        diagnostic: diagnostics.Diagnostic,
        node: torch.fx.Node,
        fx_arg: torch.fx.node.Argument,
        dtype: Optional[torch.dtype],
    ) -> torch.fx.node.Argument:
        if dtype is None:
            diagnostic.with_additional_message(
                f"Argument {fx_arg} is not promoted. Not mentioned by type promotion rule."
            )
            return fx_arg

        if isinstance(fx_arg, torch.fx.Node):
            if (old_dtype := _get_fake_tensor_val(fx_arg).dtype) != dtype:
                graph = node.graph
                with graph.inserting_before(node):
                    new_fx_arg = self._create_node(
                        graph,
                        "call_function",
                        torch.ops.prims.convert_element_type.default,
                        (fx_arg,),
                        {"dtype": dtype},
                    )
                    diagnostic.with_additional_message(
                        f"Argument {fx_arg}({old_dtype}) is promoted to {dtype}."
                    )
                    return new_fx_arg
            diagnostic.with_additional_message(
                f"Argument {fx_arg} is not promoted. Already {dtype}."
            )
            return fx_arg
        elif (
            equivalent_dtype := _SCALAR_TYPE_TENSOR_DTYPE_MAP.get(type(fx_arg), None)
        ) is not None:
            if equivalent_dtype != dtype:
                # Promote number to tensor of dtype.
                # The op should have overload that supports tensor for this arg, otherwise
                # the type promotion rule should not suggest promoting this arg.
                graph = node.graph
                with graph.inserting_before(node):
                    target = getattr(torch.ops.aten.tensor, type(fx_arg).__name__)
                    new_fx_arg = self._create_node(
                        graph, "call_function", target, (fx_arg,), {"dtype": dtype}
                    )
                    diagnostic.with_additional_message(
                        f"Argument {fx_arg}(Scalar of equivalent dtype: {equivalent_dtype}) "
                        f"is promoted to {dtype}."
                    )
                    return new_fx_arg
            diagnostic.with_additional_message(
                f"Argument {fx_arg} is not promoted. Already {dtype}."
            )
            return fx_arg
        elif isinstance(fx_arg, (tuple, list)):
            new_fx_arg = []
            diagnostic.with_additional_message(
                f"Argument {fx_arg} is a tuple/list. Promoting each element."
            )
            for fx_arg_elem in fx_arg:
                new_fx_arg.append(
                    self._explicit_type_promote_arg(
                        diagnostic, node, fx_arg_elem, dtype
                    )
                )
            return type(fx_arg)(new_fx_arg)
        else:
            raise NotImplementedError(f"Unknown fx arg type: {type(fx_arg)}")

    def _rerun_node_after_explicit_type_promotion(
        self,
        diagnostic: diagnostics.Diagnostic,
        node: torch.fx.Node,
        expected_out_dtype: torch.dtype,
    ) -> None:
        node_val = node.meta.get("val", None)
        assert node_val is not None, f"Node {node} node.meta['val'] is not set."
        args, kwargs = self.fetch_args_kwargs_from_env(node)
        node.target = find_compatible_op_overload(node, args, kwargs)

        new_node_val = self._run_node_and_update_meta_val(node)
        assert isinstance(new_node_val, type(node_val)), (
            f"run_node output type should not change between runs. "
            f"Got {type(new_node_val)}, expect {type(node_val)}."
        )

        if isinstance(node_val, torch.Tensor):
            prev_node_dtype = node_val.dtype

            assert prev_node_dtype == expected_out_dtype, (
                f"node.meta['val'].dtype({prev_node_dtype}) does not agree with "
                f"type promotion rule({expected_out_dtype})."
            )

            if new_node_val.dtype != expected_out_dtype:
                # With explicit type promotion, the expected result dtype may not be
                # the same as the computation dtype. This is referred to as "op math".
                # We need to explicitly cast the output back to the expected dtype.
                # See more about "op math" topic at `_prims_common.elementwise_dtypes`.
                graph = node.graph
                with graph.inserting_after(node):
                    output_cast_node = self._create_node(
                        graph,
                        "call_function",
                        torch.ops.prims.convert_element_type.default,
                        (node,),
                        {"dtype": expected_out_dtype},
                    )
                    node.replace_all_uses_with(output_cast_node)
                    output_cast_node.args = (node,)
                    diagnostic.with_additional_message(
                        f"Node '{node}' output dtype becomes {new_node_val.dtype} due to op math. "
                        f"Cast back to {expected_out_dtype}."
                    )

        elif isinstance(node_val, proxy_tensor.py_sym_types):
            raise NotImplementedError(
                "Type promotion does not support node output of sym types."
            )
        elif isinstance(node_val, (list, tuple)):
            raise NotImplementedError(
                "Type promotion does not support node output of list or tuple."
            )
        else:
            raise RuntimeError(f"Unexpected node output type: {type(node_val)}.")

    def _insert_explicit_type_promotion(
        self,
        diagnostic: diagnostics.Diagnostic,
        node: torch.fx.Node,
        rule: TypePromotionRule,
    ) -> None:
        args, kwargs = self.fetch_args_kwargs_from_env(node)
        type_promotion_info = rule.preview_type_promotion(args, kwargs)
        new_args = []
        new_kwargs = {}
        for i, arg in enumerate(node.args):
            new_args.append(
                self._explicit_type_promote_arg(
                    diagnostic, node, arg, type_promotion_info.args_dtypes.get(i, None)
                )
            )

        for name, arg in node.kwargs.items():
            new_kwargs[name] = self._explicit_type_promote_arg(
                diagnostic, node, arg, type_promotion_info.kwargs_dtypes.get(name, None)
            )

        # Update node
        node.args = tuple(new_args)
        node.kwargs = new_kwargs

        self._rerun_node_after_explicit_type_promotion(
            diagnostic, node, type_promotion_info.out_dtype
        )

    @diagnostics.diagnose_call(
        rule=diagnostics.rules.fx_node_explicit_type_promotion,
        level=diagnostics.levels.NONE,
    )
    def run_node(self, node: torch.fx.Node) -> Any:
        diagnostic = self.diagnostic_context.inflight_diagnostic()
        with self._set_current_node(node):
            if node.op == "call_function":
                if rule := get_type_promotion_rule(
                    diagnostic, node, self.type_promotion_table
                ):
                    self._insert_explicit_type_promotion(diagnostic, node, rule)

        return super().run_node(node)

    def _detect_fake_mode(self) -> Optional[fake_tensor.FakeTensorMode]:
        """Detect fake mode from the graph.

        Scan through all nodes in graph and their meta['val'] to detect fake mode.
        """
        fake_tensors = []
        for node in self.module.graph.nodes:
            try:
                fake_tensors.append(_get_fake_tensor_val(node))
            except RuntimeError:
                continue
        return torch._dynamo.utils.detect_fake_mode(fake_tensors)

    def _fetch_fake_args(self) -> Sequence[Optional[fake_tensor.FakeTensor]]:
        """Fetch fake args from the graph.

        For each argument, try to fetch fake tensor from the matching placeholder node.
        Return None if the fake tensor is not available.
        """
        fake_args = []
        for node in self.module.graph.nodes:
            if node.op == "placeholder":
                try:
                    fake_tensor = _get_fake_tensor_val(node)
                except RuntimeError as e:
                    if not node.users:
                        # If the placeholder is not used, we can safely ignore it and put
                        # None as placeholder.
                        fake_tensor = None
                    else:
                        raise RuntimeError(
                            "Cannot fetch symbolic fake args from fx graph. "
                            "TypePromotionPass needs to run with pre-existing fake args, "
                            "Otherwise the pass will produce inaccurate dynamic shape. "
                        ) from e

                fake_args.append(fake_tensor)
        return fake_args

    @_beartype.beartype
    def _run(self, *args, **kwargs) -> torch.fx.GraphModule:
        assert not args, (
            "`TypePromotionPass` infers symbolic fake args from graph. "
            "It does not support concrete args as arguments."
        )
        assert not kwargs, "`kwargs` is not supported"

        fake_tensor_mode = self._detect_fake_mode() or fake_tensor.FakeTensorMode(
            allow_non_fake_inputs=True
        )
        fake_args = self._fetch_fake_args()

        with fake_tensor_mode, fx_traceback.preserve_node_meta():
            torch.fx.Interpreter.run(self, *fake_args)

        return self.module
