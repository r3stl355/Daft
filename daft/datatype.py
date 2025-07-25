from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Callable, Union

from daft.context import get_context
from daft.daft import ImageMode, PyDataType, PyTimeUnit
from daft.dependencies import np, pa, pil_image

if TYPE_CHECKING:
    import builtins


class TimeUnit:
    _timeunit: PyTimeUnit

    def __init__(self) -> None:
        raise NotImplementedError("Please use TimeUnit.from_str(), .s(), .ms(), .us(), or .ns() instead.")

    @staticmethod
    def _from_pytimeunit(o3: PyTimeUnit) -> TimeUnit:
        timeunit = TimeUnit.__new__(TimeUnit)
        timeunit._timeunit = o3
        return timeunit

    @classmethod
    def s(cls) -> TimeUnit:
        """Represents seconds."""
        return cls._from_pytimeunit(PyTimeUnit.seconds())

    @classmethod
    def ms(cls) -> TimeUnit:
        """Represents milliseconds."""
        return cls._from_pytimeunit(PyTimeUnit.milliseconds())

    @classmethod
    def us(cls) -> TimeUnit:
        """Represents microseconds."""
        return cls._from_pytimeunit(PyTimeUnit.microseconds())

    @classmethod
    def ns(cls) -> TimeUnit:
        """Represents nanoseconds."""
        return cls._from_pytimeunit(PyTimeUnit.nanoseconds())

    @classmethod
    def from_str(cls, unit: str) -> TimeUnit:
        """Attempts to parse a string into a TimeUnit.

        Supported strings are
        - "s" | "seconds" -> seconds
        - "ms" | "milliseconds" -> milliseconds
        - "us" | "microseconds" -> microseconds
        - "ns" | "nanoseconds" -> nanoseconds
        Args:
            unit: The string to parse.

        Examples:
            >>> TimeUnit.from_str("s")
            TimeUnit(s)
            >>> TimeUnit.from_str("milliseconds")
            TimeUnit(ms)
            >>> try:
            ...     TimeUnit.from_str("foo")
            ... except ValueError:
            ...     pass

        """
        return cls._from_pytimeunit(PyTimeUnit.from_str(unit))

    def __str__(self) -> str:
        # These are the strings PyArrow uses.
        if self._timeunit == PyTimeUnit.seconds():
            return "s"
        elif self._timeunit == PyTimeUnit.milliseconds():
            return "ms"
        elif self._timeunit == PyTimeUnit.microseconds():
            return "us"
        elif self._timeunit == PyTimeUnit.nanoseconds():
            return "ns"
        else:
            assert False

    def __repr__(self) -> str:
        return f"TimeUnit({self.__str__()})"


class DataType:
    """A Daft DataType defines the type of all the values in an Expression or DataFrame column."""

    _dtype: PyDataType

    def __init__(self) -> None:
        raise NotImplementedError(
            "We do not support creating a DataType via __init__ "
            "use a creator method like DataType.int32() or use DataType.from_arrow_type(pa_type)"
        )

    @staticmethod
    def _infer_dtype_from_pylist(data: list[Any]) -> DataType | None:
        curr_dtype = None

        for item in data:
            if item is None:
                continue

            elif pil_image.module_available() and isinstance(item, pil_image.Image):
                item_dtype = DataType.image(item.mode)
                if curr_dtype is None:
                    curr_dtype = item_dtype
                elif not curr_dtype.is_image():
                    return None
                elif curr_dtype.image_mode and curr_dtype.image_mode != item_dtype.image_mode:
                    curr_dtype = DataType.image()
                else:
                    assert curr_dtype.image_mode == item_dtype.image_mode or curr_dtype.image_mode is None
                    pass

            elif np.module_available() and isinstance(item, (np.ndarray, np.generic)):  # type: ignore[attr-defined]
                try:
                    inner_dtype = DataType.from_numpy_dtype(item.dtype)
                except Exception:
                    return None

                shape = item.shape

                if len(shape) == 0:
                    return None
                item_dtype = DataType.list(inner_dtype) if len(shape) == 1 else DataType.tensor(inner_dtype)

                if curr_dtype is None:
                    curr_dtype = item_dtype
                elif curr_dtype != item_dtype:
                    return None
                else:
                    pass

            else:
                return None

        return curr_dtype

    @classmethod
    def _infer_type(cls, user_provided_type: DataTypeLike) -> DataType:
        from typing import get_args, get_origin

        if isinstance(user_provided_type, DataType):
            return user_provided_type
        elif isinstance(user_provided_type, dict):
            return DataType.struct({k: DataType._infer_type(user_provided_type[k]) for k in user_provided_type})
        elif get_origin(user_provided_type) is not None:
            origin_type = get_origin(user_provided_type)
            if origin_type is list:
                child_type = get_args(user_provided_type)[0]
                return DataType.list(DataType._infer_type(child_type))
            elif origin_type is dict:
                (key_type, val_type) = get_args(user_provided_type)
                return DataType.map(DataType._infer_type(key_type), DataType._infer_type(val_type))
            else:
                raise ValueError(f"Unrecognized Python origin type, cannot convert to Daft type: {origin_type}")
        elif isinstance(user_provided_type, type):
            if user_provided_type is str:
                return DataType.string()
            elif user_provided_type is int:
                return DataType.int64()
            elif user_provided_type is float:
                return DataType.float64()
            elif user_provided_type is bytes:
                return DataType.binary()
            elif user_provided_type is object:
                return DataType.python()
            else:
                raise ValueError(f"Unrecognized Python type, cannot convert to Daft type: {user_provided_type}")
        else:
            raise ValueError(f"Unable to infer Daft DataType for provided value: {user_provided_type}")

    @staticmethod
    def _from_pydatatype(pydt: PyDataType) -> DataType:
        dt = DataType.__new__(DataType)
        dt._dtype = pydt
        return dt

    @classmethod
    def int8(cls) -> DataType:
        """Create an 8-bit integer DataType."""
        return cls._from_pydatatype(PyDataType.int8())

    @classmethod
    def int16(cls) -> DataType:
        """Create an 16-bit integer DataType."""
        return cls._from_pydatatype(PyDataType.int16())

    @classmethod
    def int32(cls) -> DataType:
        """Create an 32-bit integer DataType."""
        return cls._from_pydatatype(PyDataType.int32())

    @classmethod
    def int64(cls) -> DataType:
        """Create an 64-bit integer DataType."""
        return cls._from_pydatatype(PyDataType.int64())

    @classmethod
    def uint8(cls) -> DataType:
        """Create an unsigned 8-bit integer DataType."""
        return cls._from_pydatatype(PyDataType.uint8())

    @classmethod
    def uint16(cls) -> DataType:
        """Create an unsigned 16-bit integer DataType."""
        return cls._from_pydatatype(PyDataType.uint16())

    @classmethod
    def uint32(cls) -> DataType:
        """Create an unsigned 32-bit integer DataType."""
        return cls._from_pydatatype(PyDataType.uint32())

    @classmethod
    def uint64(cls) -> DataType:
        """Create an unsigned 64-bit integer DataType."""
        return cls._from_pydatatype(PyDataType.uint64())

    @classmethod
    def float32(cls) -> DataType:
        """Create a 32-bit float DataType."""
        return cls._from_pydatatype(PyDataType.float32())

    @classmethod
    def float64(cls) -> DataType:
        """Create a 64-bit float DataType."""
        return cls._from_pydatatype(PyDataType.float64())

    @classmethod
    def string(cls) -> DataType:
        """Create a String DataType: A string of UTF8 characters."""
        return cls._from_pydatatype(PyDataType.string())

    @classmethod
    def bool(cls) -> DataType:
        """Create the Boolean DataType: Either ``True`` or ``False``."""
        return cls._from_pydatatype(PyDataType.bool())

    @classmethod
    def binary(cls) -> DataType:
        """Create a Binary DataType: A string of bytes."""
        return cls._from_pydatatype(PyDataType.binary())

    @classmethod
    def fixed_size_binary(cls, size: int) -> DataType:
        """Create a FixedSizeBinary DataType: A fixed-size string of bytes."""
        if not isinstance(size, int) or size <= 0:
            raise ValueError("The size for a fixed-size binary must be a positive integer, but got: ", size)
        return cls._from_pydatatype(PyDataType.fixed_size_binary(size))

    @classmethod
    def null(cls) -> DataType:
        """Creates the Null DataType: Always the ``Null`` value."""
        return cls._from_pydatatype(PyDataType.null())

    @classmethod
    def decimal128(cls, precision: int, scale: int) -> DataType:
        """Fixed-precision decimal."""
        return cls._from_pydatatype(PyDataType.decimal128(precision, scale))

    @classmethod
    def date(cls) -> DataType:
        """Create a Date DataType: A date with a year, month and day."""
        return cls._from_pydatatype(PyDataType.date())

    @classmethod
    def time(cls, timeunit: TimeUnit | str) -> DataType:
        """Time DataType. Supported timeunits are "us", "ns"."""
        if isinstance(timeunit, str):
            timeunit = TimeUnit.from_str(timeunit)
        return cls._from_pydatatype(PyDataType.time(timeunit._timeunit))

    @classmethod
    def timestamp(cls, timeunit: TimeUnit | str, timezone: str | None = None) -> DataType:
        """Timestamp DataType."""
        if isinstance(timeunit, str):
            timeunit = TimeUnit.from_str(timeunit)
        return cls._from_pydatatype(PyDataType.timestamp(timeunit._timeunit, timezone))

    @classmethod
    def duration(cls, timeunit: TimeUnit | str) -> DataType:
        """Duration DataType."""
        if isinstance(timeunit, str):
            timeunit = TimeUnit.from_str(timeunit)
        return cls._from_pydatatype(PyDataType.duration(timeunit._timeunit))

    @classmethod
    def interval(cls) -> DataType:
        """Interval DataType."""
        return cls._from_pydatatype(PyDataType.interval())

    @classmethod
    def list(cls, dtype: DataType) -> DataType:
        """Create a List DataType: Variable-length list, where each element in the list has type ``dtype``.

        Args:
            dtype: DataType of each element in the list
        """
        return cls._from_pydatatype(PyDataType.list(dtype._dtype))

    @classmethod
    def fixed_size_list(cls, dtype: DataType, size: int) -> DataType:
        """Create a FixedSizeList DataType: Fixed-size list, where each element in the list has type ``dtype`` and each list has length ``size``.

        Args:
            dtype: DataType of each element in the list
            size: length of each list
        """
        if not isinstance(size, int) or size <= 0:
            raise ValueError("The size for a fixed-size list must be a positive integer, but got: ", size)
        return cls._from_pydatatype(PyDataType.fixed_size_list(dtype._dtype, size))

    @classmethod
    def map(cls, key_type: DataType, value_type: DataType) -> DataType:
        """Create a Map DataType: A map is a nested type of key-value pairs that is implemented as a list of structs with two fields, key and value.

        Args:
            key_type: DataType of the keys in the map
            value_type: DataType of the values in the map
        """
        return cls._from_pydatatype(PyDataType.map(key_type._dtype, value_type._dtype))

    @classmethod
    def struct(cls, fields: dict[str, DataType]) -> DataType:
        """Create a Struct DataType: a nested type which has names mapped to child types.

        Examples:
            >>> struct_type = DataType.struct({"name": DataType.string(), "age": DataType.int64()})

        Args:
            fields: Nested fields of the Struct
        """
        return cls._from_pydatatype(PyDataType.struct({name: datatype._dtype for name, datatype in fields.items()}))

    @classmethod
    def extension(cls, name: str, storage_dtype: DataType, metadata: str | None = None) -> DataType:
        return cls._from_pydatatype(PyDataType.extension(name, storage_dtype._dtype, metadata))

    @classmethod
    def embedding(cls, dtype: DataType, size: int) -> DataType:
        """Create an Embedding DataType: embeddings are fixed size arrays, where each element in the array has a **numeric** ``dtype`` and each array has a fixed length of ``size``.

        Args:
            dtype: DataType of each element in the list (must be numeric)
            size: length of each list
        """
        if not isinstance(size, int) or size <= 0:
            raise ValueError("The size for a embedding must be a positive integer, but got: ", size)
        return cls._from_pydatatype(PyDataType.embedding(dtype._dtype, size))

    @classmethod
    def image(
        cls, mode: str | ImageMode | None = None, height: int | None = None, width: int | None = None
    ) -> DataType:
        """Create an Image DataType: image arrays contain (height, width, channel) ndarrays of pixel values.

        Each image in the array has an :class:`~daft.ImageMode`, which describes the pixel dtype (e.g. uint8) and
        the number of image channels/bands and their logical interpretation (e.g. RGB).

        If the height, width, and mode are the same for all images in the array, specifying them when constructing
        this type is advised, since that will allow Daft to create a more optimized physical representation
        of the image array.

        If the height, width, or mode may vary across images in the array, leaving these fields unspecified when
        creating this type will cause Daft to represent this image array as a heterogeneous collection of images,
        where each image can have a different mode, height, and width. This is much more flexible, but will result
        in a less compact representation and may be make some operations less efficient.

        Args:
            mode: The mode of the image. By default, this is inferred from the underlying data.
                If height and width are specified, the mode must also be specified.
            height: The height of the image. By default, this is inferred from the underlying data.
                Must be specified if the width is specified.
            width: The width of the image. By default, this is inferred from the underlying data.
                Must be specified if the width is specified.
        """
        if isinstance(mode, str):
            mode = ImageMode.from_mode_string(mode.upper())
        if mode is not None and not isinstance(mode, ImageMode):
            raise ValueError(f"mode must be a string or ImageMode variant, but got: {mode}")
        if height is not None and width is not None:
            if not isinstance(height, int) or height <= 0:
                raise ValueError("Image height must be a positive integer, but got: ", height)
            if not isinstance(width, int) or width <= 0:
                raise ValueError("Image width must be a positive integer, but got: ", width)
        elif height is not None or width is not None:
            raise ValueError(
                f"Image height and width must either both be specified, or both not be specified, but got height={height}, width={width}"
            )
        return cls._from_pydatatype(PyDataType.image(mode, height, width))

    @classmethod
    def tensor(
        cls,
        dtype: DataType,
        shape: tuple[int, ...] | None = None,
    ) -> DataType:
        """Create a tensor DataType: tensor arrays contain n-dimensional arrays of data of the provided ``dtype`` as elements, each of the provided ``shape``.

        If a ``shape`` is given, each ndarray in the column will have this shape.

        If ``shape`` is not given, the ndarrays in the column can have different shapes. This is much more flexible,
        but will result in a less compact representation and may be make some operations less efficient.

        Args:
            dtype: The type of the data contained within the tensor elements.
            shape: The shape of each tensor in the column. This is ``None`` by default, which allows the shapes of
                each tensor element to vary.
        """
        if shape is not None:
            if not isinstance(shape, tuple) or not shape or any(not isinstance(n, int) for n in shape):
                raise ValueError("Tensor shape must be a non-empty tuple of ints, but got: ", shape)
        return cls._from_pydatatype(PyDataType.tensor(dtype._dtype, shape))

    @classmethod
    def sparse_tensor(
        cls,
        dtype: DataType,
        shape: tuple[int, ...] | None = None,
        use_offset_indices: builtins.bool = False,
    ) -> DataType:
        """Create a SparseTensor DataType: SparseTensor arrays implemented as 'COO Sparse Tensor' representation of n-dimensional arrays of data of the provided ``dtype`` as elements, each of the provided ``shape``.

        If a ``shape`` is given, each ndarray in the column will have this shape.

        If ``shape`` is not given, the ndarrays in the column can have different shapes. This is much more flexible,
        but will result in a less compact representation and may be make some operations less efficient.

        The ``use_offset_indices`` parameter determines how the indices of the SparseTensor are stored:
        - ``False`` (default): Indices represent the actual positions of nonzero values.
        - ``True``: Indices represent the offsets between consecutive nonzero values.
        This can improve compression efficiency, especially when nonzero values are clustered together,
        as offsets between them are often zero, making them easier to compress.

        Args:
            dtype: The type of the data contained within the tensor elements.
            shape: The shape of each SparseTensor in the column. This is ``None`` by default, which allows the shapes of
                each tensor element to vary.
            use_offset_indices: Determines how indices are represented.
                Defaults to `False` (storing actual indices). If `True`, stores offsets between nonzero indices.
        """
        if shape is not None:
            if not isinstance(shape, tuple) or not shape or any(not isinstance(n, int) for n in shape):
                raise ValueError("SparseTensor shape must be a non-empty tuple of ints, but got: ", shape)
        return cls._from_pydatatype(PyDataType.sparse_tensor(dtype._dtype, shape, use_offset_indices))

    @classmethod
    def from_arrow_type(cls, arrow_type: pa.lib.DataType) -> DataType:
        """Maps a PyArrow DataType to a Daft DataType."""
        if pa.types.is_int8(arrow_type):
            return cls.int8()
        elif pa.types.is_int16(arrow_type):
            return cls.int16()
        elif pa.types.is_int32(arrow_type):
            return cls.int32()
        elif pa.types.is_int64(arrow_type):
            return cls.int64()
        elif pa.types.is_uint8(arrow_type):
            return cls.uint8()
        elif pa.types.is_uint16(arrow_type):
            return cls.uint16()
        elif pa.types.is_uint32(arrow_type):
            return cls.uint32()
        elif pa.types.is_uint64(arrow_type):
            return cls.uint64()
        elif pa.types.is_float32(arrow_type):
            return cls.float32()
        elif pa.types.is_float64(arrow_type):
            return cls.float64()
        elif pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type):
            return cls.string()
        elif pa.types.is_binary(arrow_type) or pa.types.is_large_binary(arrow_type):
            return cls.binary()
        elif pa.types.is_fixed_size_binary(arrow_type):
            return cls.fixed_size_binary(arrow_type.byte_width)
        elif pa.types.is_boolean(arrow_type):
            return cls.bool()
        elif pa.types.is_null(arrow_type):
            return cls.null()
        elif pa.types.is_decimal128(arrow_type):
            return cls.decimal128(arrow_type.precision, arrow_type.scale)
        elif pa.types.is_date32(arrow_type):
            return cls.date()
        elif pa.types.is_date64(arrow_type):
            return cls.timestamp(TimeUnit.ms())
        elif pa.types.is_time64(arrow_type):
            timeunit = TimeUnit.from_str(pa.type_for_alias(str(arrow_type)).unit)
            return cls.time(timeunit)
        elif pa.types.is_timestamp(arrow_type):
            timeunit = TimeUnit.from_str(arrow_type.unit)
            return cls.timestamp(timeunit=timeunit, timezone=arrow_type.tz)
        elif pa.types.is_duration(arrow_type):
            timeunit = TimeUnit.from_str(arrow_type.unit)
            return cls.duration(timeunit=timeunit)
        elif pa.types.is_list(arrow_type) or pa.types.is_large_list(arrow_type):
            assert isinstance(arrow_type, (pa.ListType, pa.LargeListType))
            field = arrow_type.value_field
            return cls.list(cls.from_arrow_type(field.type))
        elif pa.types.is_fixed_size_list(arrow_type):
            assert isinstance(arrow_type, pa.FixedSizeListType)
            field = arrow_type.value_field
            return cls.fixed_size_list(cls.from_arrow_type(field.type), arrow_type.list_size)
        elif pa.types.is_struct(arrow_type):
            assert isinstance(arrow_type, pa.StructType)
            fields = [arrow_type[i] for i in range(arrow_type.num_fields)]
            return cls.struct({field.name: cls.from_arrow_type(field.type) for field in fields})
        elif pa.types.is_interval(arrow_type):
            return cls.interval()
        elif pa.types.is_map(arrow_type):
            assert isinstance(arrow_type, pa.MapType)
            return cls.map(
                key_type=cls.from_arrow_type(arrow_type.key_type),
                value_type=cls.from_arrow_type(arrow_type.item_type),
            )
        elif isinstance(arrow_type, getattr(pa, "FixedShapeTensorType", ())):
            scalar_dtype = cls.from_arrow_type(arrow_type.value_type)
            return cls.tensor(scalar_dtype, tuple(arrow_type.shape))
        # Only check for PyExtensionType if pyarrow version is < 21.0.0
        if hasattr(pa, "PyExtensionType") and isinstance(arrow_type, getattr(pa, "PyExtensionType")):
            # TODO(Clark): Add a native cross-lang extension type representation for PyExtensionTypes.
            raise ValueError(
                "pyarrow extension types that subclass pa.PyExtensionType can't be used in Daft, since they can't be "
                f"used in non-Python Arrow implementations and Daft uses the Rust Arrow2 implementation: {arrow_type}"
            )
        elif isinstance(arrow_type, pa.BaseExtensionType):
            name = arrow_type.extension_name

            if (get_context().get_or_create_runner().name == "ray") and (
                type(arrow_type).__reduce__ == pa.BaseExtensionType.__reduce__
            ):
                raise ValueError(
                    f"You are attempting to use a Extension Type: {arrow_type} with the default pyarrow `__reduce__` which breaks pickling for Extensions"
                    "To fix this, implement your own `__reduce__` on your extension type"
                    "For more details see this issue: "
                    "https://github.com/apache/arrow/issues/35599"
                )
            try:
                metadata = arrow_type.__arrow_ext_serialize__().decode()
            except AttributeError:
                metadata = None

            if name == "daft.super_extension":
                assert metadata is not None
                return cls._from_pydatatype(PyDataType.from_json(metadata))
            else:
                return cls.extension(
                    name,
                    cls.from_arrow_type(arrow_type.storage_type),
                    metadata,
                )
        else:
            # Fall back to a Python object type.
            # TODO(Clark): Add native support for remaining Arrow types.
            return cls.python()

    @classmethod
    def from_numpy_dtype(cls, np_type: np.dtype[Any]) -> DataType:
        """Maps a Numpy datatype to a Daft DataType."""
        arrow_type = pa.from_numpy_dtype(np_type)
        return cls.from_arrow_type(arrow_type)

    def to_arrow_dtype(self) -> pa.DataType:
        return self._dtype.to_arrow()

    @classmethod
    def python(cls) -> DataType:
        """Create a Python DataType: a type which refers to an arbitrary Python object."""
        return cls._from_pydatatype(PyDataType.python())

    def is_null(self) -> builtins.bool:
        """Check if this is a null type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.null()
            >>> dtype.is_null()
            True
        """
        return self._dtype.is_null()

    def is_boolean(self) -> builtins.bool:
        """Check if this is a boolean type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.bool()
            >>> assert dtype.is_boolean()
        """
        return self._dtype.is_boolean()

    def is_int8(self) -> builtins.bool:
        """Check if this is an 8-bit integer type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.int8()
            >>> assert dtype.is_int8()
        """
        return self._dtype.is_int8()

    def is_int16(self) -> builtins.bool:
        """Check if this is a 16-bit integer type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.int16()
            >>> assert dtype.is_int16()
        """
        return self._dtype.is_int16()

    def is_int32(self) -> builtins.bool:
        """Check if this is a 32-bit integer type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.int32()
            >>> assert dtype.is_int32()
        """
        return self._dtype.is_int32()

    def is_int64(self) -> builtins.bool:
        """Check if this is a 64-bit integer type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.int64()
            >>> assert dtype.is_int64()
        """
        return self._dtype.is_int64()

    def is_uint8(self) -> builtins.bool:
        """Check if this is an unsigned 8-bit integer type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.uint8()
            >>> assert dtype.is_uint8()
        """
        return self._dtype.is_uint8()

    def is_uint16(self) -> builtins.bool:
        """Check if this is an unsigned 16-bit integer type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.uint16()
            >>> assert dtype.is_uint16()
        """
        return self._dtype.is_uint16()

    def is_uint32(self) -> builtins.bool:
        """Check if this is an unsigned 32-bit integer type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.uint32()
            >>> assert dtype.is_uint32()
        """
        return self._dtype.is_uint32()

    def is_uint64(self) -> builtins.bool:
        """Check if this is an unsigned 64-bit integer type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.uint64()
            >>> assert dtype.is_uint64()
        """
        return self._dtype.is_uint64()

    def is_float32(self) -> builtins.bool:
        """Check if this is a 32-bit float type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.float32()
            >>> assert dtype.is_float32()
        """
        return self._dtype.is_float32()

    def is_float64(self) -> builtins.bool:
        """Check if this is a 64-bit float type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.float64()
            >>> assert dtype.is_float64()
        """
        return self._dtype.is_float64()

    def is_decimal128(self) -> builtins.bool:
        """Check if this is a decimal128 type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.decimal128(precision=10, scale=2)
            >>> assert dtype.is_decimal128()
        """
        return self._dtype.is_decimal128()

    def is_timestamp(self) -> builtins.bool:
        """Check if this is a timestamp type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.timestamp(timeunit="ns")
            >>> assert dtype.is_timestamp()
        """
        return self._dtype.is_timestamp()

    def is_date(self) -> builtins.bool:
        """Check if this is a date type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.date()
            >>> assert dtype.is_date()
        """
        return self._dtype.is_date()

    def is_time(self) -> builtins.bool:
        """Check if this is a time type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.time(timeunit="ns")
            >>> assert dtype.is_time()
        """
        return self._dtype.is_time()

    def is_duration(self) -> builtins.bool:
        """Check if this is a duration type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.duration(timeunit="ns")
            >>> assert dtype.is_duration()
        """
        return self._dtype.is_duration()

    def is_interval(self) -> builtins.bool:
        """Check if this is an interval type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.interval()
            >>> assert dtype.is_interval()
        """
        return self._dtype.is_interval()

    def is_binary(self) -> builtins.bool:
        """Check if this is a binary type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.binary()
            >>> assert dtype.is_binary()
        """
        return self._dtype.is_binary()

    def is_fixed_size_binary(self) -> builtins.bool:
        """Check if this is a fixed size binary type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.fixed_size_binary(size=10)
            >>> assert dtype.is_fixed_size_binary()
        """
        return self._dtype.is_fixed_size_binary()

    def is_string(self) -> builtins.bool:
        """Check if this is a string type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.string()
            >>> assert dtype.is_string()
        """
        return self._dtype.is_string()

    def is_list(self) -> builtins.bool:
        """Check if this is a list type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.list(daft.DataType.int64())
            >>> assert dtype.is_list()
        """
        return self._dtype.is_list()

    def is_fixed_size_list(self) -> builtins.bool:
        """Check if this is a fixed size list type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.fixed_size_list(daft.DataType.int64(), size=10)
            >>> assert dtype.is_fixed_size_list()
        """
        return self._dtype.is_fixed_size_list()

    def is_struct(self) -> builtins.bool:
        """Check if this is a struct type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.struct({"a": daft.DataType.int64()})
            >>> assert dtype.is_struct()
        """
        return self._dtype.is_struct()

    def is_map(self) -> builtins.bool:
        """Check if this is a map type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.map(daft.DataType.string(), daft.DataType.int64())
            >>> assert dtype.is_map()
        """
        return self._dtype.is_map()

    def is_extension(self) -> builtins.bool:
        """Check if this is an extension type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.extension("custom", daft.DataType.int64())
            >>> assert dtype.is_extension()
        """
        return self._dtype.is_extension()

    def is_image(self) -> builtins.bool:
        """Check if this is an image type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.image()
            >>> assert dtype.is_image()
        """
        return self._dtype.is_image()

    def is_fixed_shape_image(self) -> builtins.bool:
        """Check if this is a fixed shape image type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.image(mode="RGB", height=224, width=224)
            >>> assert dtype.is_fixed_shape_image()
        """
        return self._dtype.is_fixed_shape_image()

    def is_embedding(self) -> builtins.bool:
        """Check if this is an embedding type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.embedding(daft.DataType.float32(), 512)
            >>> assert dtype.is_embedding()
        """
        return self._dtype.is_embedding()

    def is_tensor(self) -> builtins.bool:
        """Check if this is a tensor type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.tensor(daft.DataType.float32())
            >>> assert dtype.is_tensor()
        """
        return self._dtype.is_tensor()

    def is_fixed_shape_tensor(self) -> builtins.bool:
        """Check if this is a fixed shape tensor type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.tensor(daft.DataType.float32(), shape=(2, 3))
            >>> assert dtype.is_fixed_shape_tensor()
        """
        return self._dtype.is_fixed_shape_tensor()

    def is_sparse_tensor(self) -> builtins.bool:
        """Check if this is a sparse tensor type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.sparse_tensor(daft.DataType.float32())
            >>> assert dtype.is_sparse_tensor()
        """
        return self._dtype.is_sparse_tensor()

    def is_fixed_shape_sparse_tensor(self) -> builtins.bool:
        """Check if this is a fixed shape sparse tensor type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.sparse_tensor(daft.DataType.float32(), shape=(2, 3))
            >>> assert dtype.is_fixed_shape_sparse_tensor()
        """
        return self._dtype.is_fixed_shape_sparse_tensor()

    def is_python(self) -> builtins.bool:
        """Check if this is a python object type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.python()
            >>> assert dtype.is_python()
        """
        return self._dtype.is_python()

    def is_numeric(self) -> builtins.bool:
        """Check if this is a numeric type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.float64()
            >>> assert dtype.is_numeric()
        """
        return self._dtype.is_numeric()

    def is_integer(self) -> builtins.bool:
        """Check if this is an integer type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.int64()
            >>> assert dtype.is_integer()
        """
        return self._dtype.is_integer()

    def is_logical(self) -> builtins.bool:
        """Check if this is a logical type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.bool()
            >>> assert not dtype.is_logical()
        """
        return self._dtype.is_logical()

    def is_temporal(self) -> builtins.bool:
        """Check if this is a temporal type.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.timestamp(timeunit="ns")
            >>> assert dtype.is_temporal()
        """
        return self._dtype.is_temporal()

    @property
    def size(self) -> int:
        """If this is a fixed size type, return the size, otherwise an attribute error is raised.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.fixed_size_binary(size=10)
            >>> assert dtype.size == 10
            >>> dtype = daft.DataType.binary()
            >>> try:
            ...     dtype.size
            ... except AttributeError:
            ...     pass
        """
        return self._dtype.fixed_size()

    @property
    def shape(self) -> tuple[int, ...]:
        """If this is a fixed shape type, return the shape, otherwise an attribute error is raised.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.tensor(daft.DataType.float32(), shape=(2, 3))
            >>> assert dtype.shape == (2, 3)
            >>> dtype = daft.DataType.tensor(daft.DataType.float32())
            >>> try:
            ...     dtype.shape
            ... except AttributeError:
            ...     pass

        """
        return tuple(self._dtype.fixed_shape())

    @property
    def timeunit(self) -> TimeUnit:
        """If this is a time or timestamp type, return the timeunit, otherwise an attribute error is raised.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.time(timeunit="ns")
            >>> dtype.timeunit
            TimeUnit(ns)
            >>> dtype = daft.DataType.int64()
            >>> try:
            ...     dtype.timeunit
            ... except AttributeError:
            ...     pass
        """
        return TimeUnit._from_pytimeunit(self._dtype.time_unit())

    @property
    def timezone(self) -> str | None:
        """If this is a timestamp type, return the timezone, otherwise an attribute error is raised.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.timestamp(timeunit="ns", timezone="UTC")
            >>> assert dtype.timezone == "UTC"
            >>> dtype = daft.DataType.int64()
            >>> try:
            ...     dtype.time_zone
            ... except AttributeError:
            ...     pass
        """
        return self._dtype.time_zone()

    @property
    def dtype(self) -> DataType:
        """If the datatype contains an inner type, return the inner type, otherwise an attribute error is raised.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.list(daft.DataType.int64())
            >>> assert dtype.dtype == daft.DataType.int64()
            >>> dtype = daft.DataType.int64()
            >>> try:
            ...     dtype.dtype
            ... except AttributeError:
            ...     pass
        """
        return DataType._from_pydatatype(self._dtype.dtype())

    @property
    def fields(self) -> dict[str, DataType]:
        """If this is a struct type, return the fields, otherwise an attribute error is raised.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.struct({"a": daft.DataType.int64()})
            >>> fields = dtype.fields
            >>> assert fields["a"] == daft.DataType.int64()
            >>> dtype = daft.DataType.int64()
            >>> try:
            ...     dtype.fields
            ... except AttributeError:
            ...     pass
        """
        return {field.name(): DataType._from_pydatatype(field.dtype()) for field in self._dtype.fields()}

    @property
    def precision(self) -> int:
        """If this is a decimal type, return the precision, otherwise an attribute error is raised.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.decimal128(precision=10, scale=2)
            >>> assert dtype.precision == 10
            >>> dtype = daft.DataType.int64()
            >>> try:
            ...     dtype.precision
            ... except AttributeError:
            ...     pass
        """
        return self._dtype.precision()

    @property
    def scale(self) -> int:
        """If this is a decimal type, return the scale, otherwise an attribute error is raised.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.decimal128(precision=10, scale=2)
            >>> assert dtype.scale == 2
            >>> dtype = daft.DataType.int64()
            >>> try:
            ...     dtype.precision
            ... except AttributeError:
            ...     pass
        """
        return self._dtype.scale()

    @property
    def image_mode(self) -> ImageMode | None:
        """If this is an image type, return the (optional) image mode, otherwise an attribute error is raised.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.image(mode="RGB")
            >>> assert dtype.image_mode == daft.ImageMode.RGB
            >>> dtype = daft.DataType.int64()
            >>> try:
            ...     dtype.image_mode
            ... except AttributeError:
            ...     pass
        """
        return self._dtype.image_mode()

    @property
    def use_offset_indices(self) -> builtins.bool:
        """If this is a sparse tensor type, return whether the indices are stored as offsets, otherwise an attribute error is raised.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.sparse_tensor(daft.DataType.float32(), use_offset_indices=True)
            >>> assert dtype.use_offset_indices
            >>> dtype = daft.DataType.int64()
            >>> try:
            ...     dtype.use_offset_indices
            ... except AttributeError:
            ...     pass
        """
        return self._dtype.use_offset_indices()

    @property
    def key_type(self) -> DataType:
        """If this is a map type, return the key type, otherwise an attribute error is raised.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.map(daft.DataType.string(), daft.DataType.int64())
            >>> assert dtype.key_type == daft.DataType.string()
            >>> dtype = daft.DataType.int64()
            >>> try:
            ...     dtype.key_type
            ... except AttributeError:
            ...     pass
        """
        return DataType._from_pydatatype(self._dtype.key_type())

    @property
    def value_type(self) -> DataType:
        """If this is a map type, return the value type, otherwise an attribute error is raised.

        Examples:
            >>> import daft
            >>> dtype = daft.DataType.map(daft.DataType.string(), daft.DataType.int64())
            >>> assert dtype.value_type == daft.DataType.int64()
            >>> dtype = daft.DataType.int64()
            >>> try:
            ...     dtype.value_type
            ... except AttributeError:
            ...     pass
        """
        return DataType._from_pydatatype(self._dtype.value_type())

    def _should_cast_to_python(self) -> builtins.bool:
        # NOTE: This is used to determine if we should cast a column to a Python object type when converting to PyList.
        # Map is a logical type, but we don't want to cast it to Python because the underlying physical type is a List,
        # which we can handle without casting to Python.
        return self.is_logical() and not self.is_map()

    def __repr__(self) -> str:
        return self._dtype.__repr__()

    def __eq__(self, other: object) -> builtins.bool:
        return isinstance(other, DataType) and self._dtype.is_equal(other._dtype)

    def __reduce__(self) -> tuple[Callable[[PyDataType], DataType], tuple[PyDataType]]:
        return DataType._from_pydatatype, (self._dtype,)

    def __hash__(self) -> int:
        return self._dtype.__hash__()


# Type alias for a union of types that can be inferred into a DataType
DataTypeLike = Union[DataType, type, str]


_EXT_TYPE_REGISTRATION_LOCK = threading.Lock()
_EXT_TYPE_REGISTERED = False
_STATIC_DAFT_EXTENSION: pa.ExtensionType | None = None


def _ensure_registered_super_ext_type() -> None:
    global _EXT_TYPE_REGISTERED
    global _STATIC_DAFT_EXTENSION

    # Double-checked locking: avoid grabbing the lock if we know that the ext type
    # has already been registered.
    if not _EXT_TYPE_REGISTERED:
        with _EXT_TYPE_REGISTRATION_LOCK:
            if not _EXT_TYPE_REGISTERED:

                class DaftExtension(pa.ExtensionType):  # type: ignore[misc]
                    def __init__(self, dtype: pa.DataType, metadata: bytes = b"") -> None:
                        # attributes need to be set first before calling
                        # super init (as that calls serialize)
                        self._metadata = metadata
                        super().__init__(dtype, "daft.super_extension")

                    def __reduce__(
                        self,
                    ) -> tuple[Callable[[pa.DataType, bytes], DaftExtension], tuple[pa.DataType, bytes]]:
                        return type(self).__arrow_ext_deserialize__, (self.storage_type, self.__arrow_ext_serialize__())

                    def __arrow_ext_serialize__(self) -> bytes:
                        return self._metadata

                    @classmethod
                    def __arrow_ext_deserialize__(cls, storage_type: pa.DataType, serialized: bytes) -> DaftExtension:
                        return cls(storage_type, serialized)

                _STATIC_DAFT_EXTENSION = DaftExtension
                pa.register_extension_type(DaftExtension(pa.null()))
                import atexit

                atexit.register(lambda: pa.unregister_extension_type("daft.super_extension"))
                _EXT_TYPE_REGISTERED = True


def get_super_ext_type() -> type[pa.ExtensionType]:
    _ensure_registered_super_ext_type()
    assert _STATIC_DAFT_EXTENSION is not None
    return _STATIC_DAFT_EXTENSION
