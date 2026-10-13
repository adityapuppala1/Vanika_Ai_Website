# InvestorDesk/config.py
# Re-export central configuration from parent config module
from config import (
    settings,
    investors_profiles,
    investors_content,
    ensure_indexes,
    azure_blob_service_client,
    azure_container_name,
    AZURE_ACCOUNT_NAME,
    AZURE_ACCOUNT_KEY,
    parse_connection_string,
    setup_initial_schema,
    print_mongo_collections,
    get_collection_data
)

__all__ = [
    "settings",
    "investors_profiles",
    "investors_content",
    "ensure_indexes",
    "azure_blob_service_client",
    "azure_container_name",
    "AZURE_ACCOUNT_NAME",
    "AZURE_ACCOUNT_KEY",
    "parse_connection_string",
    "setup_initial_schema",
    "print_mongo_collections",
    "get_collection_data"
]
