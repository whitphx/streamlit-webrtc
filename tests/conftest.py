def setup_runtime():
    """`streamlit.components.v1.components.declare_component()` requires a Streamlit Runtime instance exists since Streamlit 1.34.0,
    so we instantiate it here before all tests.
    This code is based on https://github.com/streamlit/streamlit/blob/1.34.0/lib/streamlit/web/server/server.py#L228-L251
    """
    from streamlit.runtime import Runtime, RuntimeConfig
    from streamlit.runtime.memory_media_file_storage import MemoryMediaFileStorage
    from streamlit.runtime.memory_uploaded_file_manager import MemoryUploadedFileManager
    from streamlit.web.cache_storage_manager_config import (
        create_default_cache_storage_manager,
    )
    from streamlit.web.server.media_file_handler import MediaFileHandler

    MEDIA_ENDPOINT = "/media"
    UPLOAD_FILE_ENDPOINT = "/_stcore/upload_file"

    # Initialize MediaFileStorage and its associated endpoint
    media_file_storage = MemoryMediaFileStorage(MEDIA_ENDPOINT)
    MediaFileHandler.initialize_storage(media_file_storage)

    uploaded_file_mgr = MemoryUploadedFileManager(UPLOAD_FILE_ENDPOINT)

    main_script_path = ""

    return Runtime(
        RuntimeConfig(
            script_path=main_script_path,
            command_line=None,
            media_file_storage=media_file_storage,
            uploaded_file_manager=uploaded_file_mgr,
            cache_storage_manager=create_default_cache_storage_manager(),
            is_hello=False,
        )
    )


setup_runtime()
