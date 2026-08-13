from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ServingState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SERVING_STATE_UNSPECIFIED: _ClassVar[ServingState]
    SERVING_STATE_READY: _ClassVar[ServingState]
    SERVING_STATE_DEGRADED: _ClassVar[ServingState]
    SERVING_STATE_UNHEALTHY: _ClassVar[ServingState]

class RuntimeModelState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RUNTIME_MODEL_STATE_UNSPECIFIED: _ClassVar[RuntimeModelState]
    RUNTIME_MODEL_STATE_INSTALLED: _ClassVar[RuntimeModelState]
    RUNTIME_MODEL_STATE_LOADING: _ClassVar[RuntimeModelState]
    RUNTIME_MODEL_STATE_READY: _ClassVar[RuntimeModelState]
    RUNTIME_MODEL_STATE_FAILED: _ClassVar[RuntimeModelState]

class LocalArtifactOperation(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    LOCAL_ARTIFACT_OPERATION_UNSPECIFIED: _ClassVar[LocalArtifactOperation]
    LOCAL_ARTIFACT_OPERATION_READ: _ClassVar[LocalArtifactOperation]
    LOCAL_ARTIFACT_OPERATION_WRITE: _ClassVar[LocalArtifactOperation]

class RuntimeFailureClass(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RUNTIME_FAILURE_CLASS_UNSPECIFIED: _ClassVar[RuntimeFailureClass]
    RUNTIME_FAILURE_CLASS_INPUT: _ClassVar[RuntimeFailureClass]
    RUNTIME_FAILURE_CLASS_MODEL_LOAD: _ClassVar[RuntimeFailureClass]
    RUNTIME_FAILURE_CLASS_INFERENCE: _ClassVar[RuntimeFailureClass]
    RUNTIME_FAILURE_CLASS_GPU_RESOURCE: _ClassVar[RuntimeFailureClass]
    RUNTIME_FAILURE_CLASS_LOCAL_STORAGE: _ClassVar[RuntimeFailureClass]
    RUNTIME_FAILURE_CLASS_RUNTIME: _ClassVar[RuntimeFailureClass]
    RUNTIME_FAILURE_CLASS_CANCELED: _ClassVar[RuntimeFailureClass]

class CancelDisposition(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CANCEL_DISPOSITION_UNSPECIFIED: _ClassVar[CancelDisposition]
    CANCEL_DISPOSITION_ACCEPTED: _ClassVar[CancelDisposition]
    CANCEL_DISPOSITION_ALREADY_TERMINAL: _ClassVar[CancelDisposition]
    CANCEL_DISPOSITION_NOT_FOUND: _ClassVar[CancelDisposition]
SERVING_STATE_UNSPECIFIED: ServingState
SERVING_STATE_READY: ServingState
SERVING_STATE_DEGRADED: ServingState
SERVING_STATE_UNHEALTHY: ServingState
RUNTIME_MODEL_STATE_UNSPECIFIED: RuntimeModelState
RUNTIME_MODEL_STATE_INSTALLED: RuntimeModelState
RUNTIME_MODEL_STATE_LOADING: RuntimeModelState
RUNTIME_MODEL_STATE_READY: RuntimeModelState
RUNTIME_MODEL_STATE_FAILED: RuntimeModelState
LOCAL_ARTIFACT_OPERATION_UNSPECIFIED: LocalArtifactOperation
LOCAL_ARTIFACT_OPERATION_READ: LocalArtifactOperation
LOCAL_ARTIFACT_OPERATION_WRITE: LocalArtifactOperation
RUNTIME_FAILURE_CLASS_UNSPECIFIED: RuntimeFailureClass
RUNTIME_FAILURE_CLASS_INPUT: RuntimeFailureClass
RUNTIME_FAILURE_CLASS_MODEL_LOAD: RuntimeFailureClass
RUNTIME_FAILURE_CLASS_INFERENCE: RuntimeFailureClass
RUNTIME_FAILURE_CLASS_GPU_RESOURCE: RuntimeFailureClass
RUNTIME_FAILURE_CLASS_LOCAL_STORAGE: RuntimeFailureClass
RUNTIME_FAILURE_CLASS_RUNTIME: RuntimeFailureClass
RUNTIME_FAILURE_CLASS_CANCELED: RuntimeFailureClass
CANCEL_DISPOSITION_UNSPECIFIED: CancelDisposition
CANCEL_DISPOSITION_ACCEPTED: CancelDisposition
CANCEL_DISPOSITION_ALREADY_TERMINAL: CancelDisposition
CANCEL_DISPOSITION_NOT_FOUND: CancelDisposition

class ExecuteResponse(_message.Message):
    __slots__ = ("event",)
    EVENT_FIELD_NUMBER: _ClassVar[int]
    event: ExecutionEvent
    def __init__(self, event: _Optional[_Union[ExecutionEvent, _Mapping]] = ...) -> None: ...

class HealthRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HealthResponse(_message.Message):
    __slots__ = ("state", "runtime_version", "adapter_version", "health_flags")
    STATE_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_VERSION_FIELD_NUMBER: _ClassVar[int]
    ADAPTER_VERSION_FIELD_NUMBER: _ClassVar[int]
    HEALTH_FLAGS_FIELD_NUMBER: _ClassVar[int]
    state: ServingState
    runtime_version: str
    adapter_version: str
    health_flags: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, state: _Optional[_Union[ServingState, str]] = ..., runtime_version: _Optional[str] = ..., adapter_version: _Optional[str] = ..., health_flags: _Optional[_Iterable[str]] = ...) -> None: ...

class GetCapabilitiesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetCapabilitiesResponse(_message.Message):
    __slots__ = ("runtime_version", "adapter_version", "devices", "models")
    RUNTIME_VERSION_FIELD_NUMBER: _ClassVar[int]
    ADAPTER_VERSION_FIELD_NUMBER: _ClassVar[int]
    DEVICES_FIELD_NUMBER: _ClassVar[int]
    MODELS_FIELD_NUMBER: _ClassVar[int]
    runtime_version: str
    adapter_version: str
    devices: _containers.RepeatedCompositeFieldContainer[RuntimeDevice]
    models: _containers.RepeatedCompositeFieldContainer[RuntimeModel]
    def __init__(self, runtime_version: _Optional[str] = ..., adapter_version: _Optional[str] = ..., devices: _Optional[_Iterable[_Union[RuntimeDevice, _Mapping]]] = ..., models: _Optional[_Iterable[_Union[RuntimeModel, _Mapping]]] = ...) -> None: ...

class RuntimeDevice(_message.Message):
    __slots__ = ("device_id", "hardware_class", "total_vram_bytes", "total_slots", "free_slots")
    DEVICE_ID_FIELD_NUMBER: _ClassVar[int]
    HARDWARE_CLASS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_VRAM_BYTES_FIELD_NUMBER: _ClassVar[int]
    TOTAL_SLOTS_FIELD_NUMBER: _ClassVar[int]
    FREE_SLOTS_FIELD_NUMBER: _ClassVar[int]
    device_id: str
    hardware_class: str
    total_vram_bytes: int
    total_slots: int
    free_slots: int
    def __init__(self, device_id: _Optional[str] = ..., hardware_class: _Optional[str] = ..., total_vram_bytes: _Optional[int] = ..., total_slots: _Optional[int] = ..., free_slots: _Optional[int] = ...) -> None: ...

class RuntimeModel(_message.Message):
    __slots__ = ("catalog_model_id", "model_version", "model_digest", "precisions", "features", "state")
    CATALOG_MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    MODEL_VERSION_FIELD_NUMBER: _ClassVar[int]
    MODEL_DIGEST_FIELD_NUMBER: _ClassVar[int]
    PRECISIONS_FIELD_NUMBER: _ClassVar[int]
    FEATURES_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    catalog_model_id: str
    model_version: str
    model_digest: str
    precisions: _containers.RepeatedScalarFieldContainer[str]
    features: _containers.RepeatedScalarFieldContainer[str]
    state: RuntimeModelState
    def __init__(self, catalog_model_id: _Optional[str] = ..., model_version: _Optional[str] = ..., model_digest: _Optional[str] = ..., precisions: _Optional[_Iterable[str]] = ..., features: _Optional[_Iterable[str]] = ..., state: _Optional[_Union[RuntimeModelState, str]] = ...) -> None: ...

class ExecuteRequest(_message.Message):
    __slots__ = ("job_id", "attempt_id", "device_id", "slot_id", "model", "parameters", "inputs", "outputs", "deadline_unix_ms", "maximum_preview_bytes")
    class ParametersEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: ParameterValue
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[ParameterValue, _Mapping]] = ...) -> None: ...
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    ATTEMPT_ID_FIELD_NUMBER: _ClassVar[int]
    DEVICE_ID_FIELD_NUMBER: _ClassVar[int]
    SLOT_ID_FIELD_NUMBER: _ClassVar[int]
    MODEL_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    INPUTS_FIELD_NUMBER: _ClassVar[int]
    OUTPUTS_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    MAXIMUM_PREVIEW_BYTES_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    attempt_id: str
    device_id: str
    slot_id: str
    model: ModelSpec
    parameters: _containers.MessageMap[str, ParameterValue]
    inputs: _containers.RepeatedCompositeFieldContainer[LocalArtifact]
    outputs: _containers.RepeatedCompositeFieldContainer[LocalArtifact]
    deadline_unix_ms: int
    maximum_preview_bytes: int
    def __init__(self, job_id: _Optional[str] = ..., attempt_id: _Optional[str] = ..., device_id: _Optional[str] = ..., slot_id: _Optional[str] = ..., model: _Optional[_Union[ModelSpec, _Mapping]] = ..., parameters: _Optional[_Mapping[str, ParameterValue]] = ..., inputs: _Optional[_Iterable[_Union[LocalArtifact, _Mapping]]] = ..., outputs: _Optional[_Iterable[_Union[LocalArtifact, _Mapping]]] = ..., deadline_unix_ms: _Optional[int] = ..., maximum_preview_bytes: _Optional[int] = ...) -> None: ...

class ModelSpec(_message.Message):
    __slots__ = ("catalog_model_id", "model_version", "model_digest", "precision")
    CATALOG_MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    MODEL_VERSION_FIELD_NUMBER: _ClassVar[int]
    MODEL_DIGEST_FIELD_NUMBER: _ClassVar[int]
    PRECISION_FIELD_NUMBER: _ClassVar[int]
    catalog_model_id: str
    model_version: str
    model_digest: str
    precision: str
    def __init__(self, catalog_model_id: _Optional[str] = ..., model_version: _Optional[str] = ..., model_digest: _Optional[str] = ..., precision: _Optional[str] = ...) -> None: ...

class ParameterValue(_message.Message):
    __slots__ = ("string_value", "integer_value", "number_value", "boolean_value")
    STRING_VALUE_FIELD_NUMBER: _ClassVar[int]
    INTEGER_VALUE_FIELD_NUMBER: _ClassVar[int]
    NUMBER_VALUE_FIELD_NUMBER: _ClassVar[int]
    BOOLEAN_VALUE_FIELD_NUMBER: _ClassVar[int]
    string_value: str
    integer_value: int
    number_value: float
    boolean_value: bool
    def __init__(self, string_value: _Optional[str] = ..., integer_value: _Optional[int] = ..., number_value: _Optional[float] = ..., boolean_value: _Optional[bool] = ...) -> None: ...

class LocalArtifact(_message.Message):
    __slots__ = ("artifact_id", "local_handle", "operation", "expected_size_bytes", "expected_sha256", "media_type")
    ARTIFACT_ID_FIELD_NUMBER: _ClassVar[int]
    LOCAL_HANDLE_FIELD_NUMBER: _ClassVar[int]
    OPERATION_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_SHA256_FIELD_NUMBER: _ClassVar[int]
    MEDIA_TYPE_FIELD_NUMBER: _ClassVar[int]
    artifact_id: str
    local_handle: str
    operation: LocalArtifactOperation
    expected_size_bytes: int
    expected_sha256: str
    media_type: str
    def __init__(self, artifact_id: _Optional[str] = ..., local_handle: _Optional[str] = ..., operation: _Optional[_Union[LocalArtifactOperation, str]] = ..., expected_size_bytes: _Optional[int] = ..., expected_sha256: _Optional[str] = ..., media_type: _Optional[str] = ...) -> None: ...

class ExecutionEvent(_message.Message):
    __slots__ = ("job_id", "attempt_id", "sequence", "observed_at_unix_ms", "started", "progress", "preview", "completed", "failed", "canceled")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    ATTEMPT_ID_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    OBSERVED_AT_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    STARTED_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    PREVIEW_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_FIELD_NUMBER: _ClassVar[int]
    FAILED_FIELD_NUMBER: _ClassVar[int]
    CANCELED_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    attempt_id: str
    sequence: int
    observed_at_unix_ms: int
    started: ExecutionStarted
    progress: ExecutionProgress
    preview: PreviewChunk
    completed: ExecutionCompleted
    failed: ExecutionFailed
    canceled: ExecutionCanceled
    def __init__(self, job_id: _Optional[str] = ..., attempt_id: _Optional[str] = ..., sequence: _Optional[int] = ..., observed_at_unix_ms: _Optional[int] = ..., started: _Optional[_Union[ExecutionStarted, _Mapping]] = ..., progress: _Optional[_Union[ExecutionProgress, _Mapping]] = ..., preview: _Optional[_Union[PreviewChunk, _Mapping]] = ..., completed: _Optional[_Union[ExecutionCompleted, _Mapping]] = ..., failed: _Optional[_Union[ExecutionFailed, _Mapping]] = ..., canceled: _Optional[_Union[ExecutionCanceled, _Mapping]] = ...) -> None: ...

class ExecutionStarted(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ExecutionProgress(_message.Message):
    __slots__ = ("progress_permille", "stage_code")
    PROGRESS_PERMILLE_FIELD_NUMBER: _ClassVar[int]
    STAGE_CODE_FIELD_NUMBER: _ClassVar[int]
    progress_permille: int
    stage_code: str
    def __init__(self, progress_permille: _Optional[int] = ..., stage_code: _Optional[str] = ...) -> None: ...

class PreviewChunk(_message.Message):
    __slots__ = ("sequence", "media_type", "data")
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    MEDIA_TYPE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    sequence: int
    media_type: str
    data: bytes
    def __init__(self, sequence: _Optional[int] = ..., media_type: _Optional[str] = ..., data: _Optional[bytes] = ...) -> None: ...

class ExecutionCompleted(_message.Message):
    __slots__ = ("outputs", "measurements")
    OUTPUTS_FIELD_NUMBER: _ClassVar[int]
    MEASUREMENTS_FIELD_NUMBER: _ClassVar[int]
    outputs: _containers.RepeatedCompositeFieldContainer[LocalArtifactManifest]
    measurements: RuntimeMeasurements
    def __init__(self, outputs: _Optional[_Iterable[_Union[LocalArtifactManifest, _Mapping]]] = ..., measurements: _Optional[_Union[RuntimeMeasurements, _Mapping]] = ...) -> None: ...

class LocalArtifactManifest(_message.Message):
    __slots__ = ("artifact_id", "local_handle", "size_bytes", "sha256", "media_type", "duration_ms")
    ARTIFACT_ID_FIELD_NUMBER: _ClassVar[int]
    LOCAL_HANDLE_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    SHA256_FIELD_NUMBER: _ClassVar[int]
    MEDIA_TYPE_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    artifact_id: str
    local_handle: str
    size_bytes: int
    sha256: str
    media_type: str
    duration_ms: int
    def __init__(self, artifact_id: _Optional[str] = ..., local_handle: _Optional[str] = ..., size_bytes: _Optional[int] = ..., sha256: _Optional[str] = ..., media_type: _Optional[str] = ..., duration_ms: _Optional[int] = ...) -> None: ...

class ExecutionFailed(_message.Message):
    __slots__ = ("failure_class", "stable_code", "safe_detail", "measurements")
    FAILURE_CLASS_FIELD_NUMBER: _ClassVar[int]
    STABLE_CODE_FIELD_NUMBER: _ClassVar[int]
    SAFE_DETAIL_FIELD_NUMBER: _ClassVar[int]
    MEASUREMENTS_FIELD_NUMBER: _ClassVar[int]
    failure_class: RuntimeFailureClass
    stable_code: str
    safe_detail: str
    measurements: RuntimeMeasurements
    def __init__(self, failure_class: _Optional[_Union[RuntimeFailureClass, str]] = ..., stable_code: _Optional[str] = ..., safe_detail: _Optional[str] = ..., measurements: _Optional[_Union[RuntimeMeasurements, _Mapping]] = ...) -> None: ...

class ExecutionCanceled(_message.Message):
    __slots__ = ("measurements",)
    MEASUREMENTS_FIELD_NUMBER: _ClassVar[int]
    measurements: RuntimeMeasurements
    def __init__(self, measurements: _Optional[_Union[RuntimeMeasurements, _Mapping]] = ...) -> None: ...

class RuntimeMeasurements(_message.Message):
    __slots__ = ("normalized_input_characters", "input_audio_ms", "output_audio_ms", "gpu_execution_ms", "cpu_execution_ms")
    NORMALIZED_INPUT_CHARACTERS_FIELD_NUMBER: _ClassVar[int]
    INPUT_AUDIO_MS_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_AUDIO_MS_FIELD_NUMBER: _ClassVar[int]
    GPU_EXECUTION_MS_FIELD_NUMBER: _ClassVar[int]
    CPU_EXECUTION_MS_FIELD_NUMBER: _ClassVar[int]
    normalized_input_characters: int
    input_audio_ms: int
    output_audio_ms: int
    gpu_execution_ms: int
    cpu_execution_ms: int
    def __init__(self, normalized_input_characters: _Optional[int] = ..., input_audio_ms: _Optional[int] = ..., output_audio_ms: _Optional[int] = ..., gpu_execution_ms: _Optional[int] = ..., cpu_execution_ms: _Optional[int] = ...) -> None: ...

class CancelRequest(_message.Message):
    __slots__ = ("job_id", "attempt_id", "reason_code", "deadline_unix_ms")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    ATTEMPT_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_CODE_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    attempt_id: str
    reason_code: str
    deadline_unix_ms: int
    def __init__(self, job_id: _Optional[str] = ..., attempt_id: _Optional[str] = ..., reason_code: _Optional[str] = ..., deadline_unix_ms: _Optional[int] = ...) -> None: ...

class CancelResponse(_message.Message):
    __slots__ = ("disposition",)
    DISPOSITION_FIELD_NUMBER: _ClassVar[int]
    disposition: CancelDisposition
    def __init__(self, disposition: _Optional[_Union[CancelDisposition, str]] = ...) -> None: ...
