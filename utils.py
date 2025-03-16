from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_experimental.sql.base import SQLDatabaseChain
from langchain_core.output_parsers import StrOutputParser
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory

import configparser
import os
import clickhouse_connect
from sqlalchemy import create_engine

def read_properties_file(file_path):
    """Reads database credentials and API key from the properties file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ The file '{file_path}' does not exist.")

    config = configparser.ConfigParser()
    config.read(file_path)

    if "DEFAULT" not in config:
        raise KeyError("❌ Missing 'DEFAULT' section in config file. Ensure the file is correctly formatted.")

    required_keys = ["db_host", "db_port", "db_user", "db_password", "db_name", "gemini_api_key"]
    missing_keys = [key for key in required_keys if key not in config["DEFAULT"]]

    if missing_keys:
        raise KeyError(f"❌ Missing keys in config file: {', '.join(missing_keys)}")

    return {
        "db_host": config["DEFAULT"]["db_host"],
        "db_port": int(config["DEFAULT"]["db_port"]),
        "db_user": config["DEFAULT"]["db_user"],
        "db_password": config["DEFAULT"]["db_password"],
        "db_name": config["DEFAULT"]["db_name"],
        "gemini_api_key": config["DEFAULT"]["gemini_api_key"]
    }

def get_property():
    """Retrieves database properties from the config file."""
    file_path = "config.properties"
    try:
        return read_properties_file(file_path)
    except Exception as e:
        print(f"❌ Error reading config file: {e}")
        raise e

def get_llm(gemini_api_key):
    """Creates an instance of Google Gemini Pro LLM."""
    try:
        llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",  # Or "gemini-1.5-flash" , "gemini-1.5-pro"
    google_api_key=gemini_api_key,
    api_version="v1",
    convert_system_message_to_human=True,
    temperature=0.0
)
        print("✅ Google Gemini Pro LLM Initialized Successfully.")
        return llm
    except Exception as e:
        print(f"❌ Error initializing LLM: {e}")
        raise e

def db_connection(db_host, db_port, db_user, db_password, db_name):
    """Establishes a connection to ClickHouse using SQLAlchemy."""
    connection_string = f"clickhouse+http://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    try:
        engine = create_engine(connection_string)
        connection = engine.connect()
        print("✅ Connected to ClickHouse successfully")

        # Fetch table names
        client = clickhouse_connect.get_client(host=db_host, port=db_port, username=db_user, password=db_password)
        tables = client.query("SHOW TABLES").result_rows
        print("Available Tables:", tables)

        # Validate if 'combined_definition_map' exists
        table_names = [t[0] for t in tables]  
        if 'combined_definition_map' not in table_names:
            raise ValueError(f"❌ Table 'combined_definition_map' does not exist in the database. Available tables: {table_names}")

        return SQLDatabase(engine)
    
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        raise e

def create_conversational_chain():
    try:
        # Fetch properties from the config file
        config = get_property()

        # Get the LLM instance
        llm = get_llm(config["gemini_api_key"])

        # Get the DB connection
        db = db_connection(
            config["db_host"],
            config["db_port"],
            config["db_user"],
            config["db_password"],
            config["db_name"]
        )

        sql_prompt_template = """
        Only use the following tables:
        {table_info}
        Question: {input}

        Given an input question, first create a syntactically correct
        {dialect} query to run.
        
        Relevant pieces of previous conversation:
        {history}

        (You do not need to use these pieces of information if not relevant)
        Don't include ```, ```sql and \n in the output.
        """
        prompt = PromptTemplate(
            input_variables=["input", "table_info", "dialect", "history"],
            template=sql_prompt_template,
        )
        memory = ConversationBufferMemory(memory_key="history")

        db_chain = SQLDatabaseChain.from_llm(
            llm, db, memory=memory, prompt=prompt, return_direct=True, verbose=True
        )

        output_parser = StrOutputParser()
        chain = llm | output_parser

    except Exception as e:
        print(f"❌ Error in creating conversational chain: {e}")
        raise e
    
    return db_chain, chain

# Entry Point
if __name__ == "__main__":
    try:
        db_chain, chain = create_conversational_chain()
    except Exception as e:
        print(f"❌ Execution failed: {e}")
