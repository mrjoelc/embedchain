import hashlib
import json
from plistlib import UID
from string import Template
from typing import Optional
from embedchain.config import AddConfig
#from embedchain.config.AddConfig import ChunkerConfig
#from embedchain.config.apps.AppConfig import AppConfig
#from embedchain.config.vectordbs.ChromaDbConfig import ChromaDbConfig
from flask import Flask, jsonify, request
import uuid
import ast
import os
import traceback

from embedchain import App
from embedchain.config.add_config import ChunkerConfig
from embedchain.config.app_config import AppConfig
from embedchain.config.llm.base import BaseLlmConfig
from embedchain.config.vectordb.chroma import ChromaDbConfig
from embedchain.vectordb.chroma import ChromaDB

app = Flask(__name__)



def initialize_chat_bot():
    global chat_bots 
    global hash_source_dict
    if os.path.exists("/db/dict/hash_source_dict.json"):
        with open('/db/dict/hash_source_dict.json', 'r') as json_file:
            hash_source_dict = dict(json.load(json_file))
    else:
        hash_source_dict = {}
    
    chat_bots = {}
    bot_directory_path = "/db/bots"
    for filename in os.listdir(bot_directory_path):
        # Check if the item is a file (not a subdirectory)
        if os.path.isfile(os.path.join(bot_directory_path, filename)):
            #chat_bots[filename] = App.load_from_file(bot_directory_path + "/" + filename)
                db_bot_config = ChromaDbConfig(collection_name=filename, dir="/db/")
                db = ChromaDB(config=db_bot_config)
                app_config = AppConfig(collect_metrics=False)
                chat_bots[filename] = App(config=app_config, db=db)

    

    # if os.path.exists("/db/helloworld.txt"):
    #     app.logger.debug("yes exist!")
    # else:
    #     app.logger.debug("no, sorry!")

def get_key_from_value(dictionary, search_value):
    for key, value in dictionary.items():
        if value == search_value:
            return key
    # If the value is not found, you can return a default value or raise an exception.
    return None


@app.route("/bot", methods=["DELETE"])
def delete_bot():
    data = request.get_json()
    bot_id = data.get("bot_id", {})
    if len(bot_id) >= 1:
        if bot_id in chat_bots:
            del chat_bots[bot_id]
            os.remove("/db/bots/"+bot_id)
            return jsonify({"data": f"{bot_id} deleted"}), 200
        else:
            return jsonify({"error": "Invalid request. The bot_id provided does not exist."}), 400
    else:
        return jsonify({"error": "Invalid request. Please provide a valid bot_id."}), 400
    


@app.route("/doc", methods=["DELETE"])
def delete_doc():
    data = request.get_json()
    bot_id = data.get("bot_id", {})
    chat_bot:App = None
    if len(bot_id) >= 1:
        if bot_id in chat_bots:
            chat_bot = chat_bots.get(bot_id)
        else:
            return jsonify({"error": "Invalid request. The bot_id provided does not exist."}), 400
    else:
        return jsonify({"error": "Invalid request. Please provide a valid bot_id."}), 400
    
    source = data.get("source", {})

    if len(source) >= 1:
        try:
            question = source.get("question",{})
            answer = source.get("answer",{})
            if len(question)>1 and len(answer)>1:
                source = (question, answer)
        except:
            pass
  
        # `source_id` is the hash of the source argument
        hash_object = hashlib.md5(str(source).encode("utf-8"))
        source_id = hash_object.hexdigest()

        if len(chat_bot.db.get(where={'hash':source_id})['ids'])>0:
            chat_bot.db.delete({'hash':source_id})
            if len(chat_bot.db.get(where={'hash':source_id})['ids'])==0:
                return jsonify({"data": f"source {source} deleted"}), 200
            else:
                return jsonify({"error": "Impossible to delete the document."}), 400
        else:
            return jsonify({"error": "Invalid request. The source provided does not exist."}), 400
    else:
        return jsonify({"error": "Invalid request. Please provide a valid source."}), 400
    

@app.route("/new_bot", methods=["POST"])
def new_bot():
    data = request.get_json()
    #app.logger.debug(data)
    bot_id = data.get("bot_id", {})
    if len(bot_id) < 1:
        return jsonify({"error": "Invalid request. Please provide a valid bot_id."}), 400
        # bot_id = str(uuid.uuid4())
    elif len(bot_id) < 3:
        return jsonify({"error": "Invalid request. Please provide a bot_id longer that 2 characters."}), 400
    if bot_id in chat_bots:
        return jsonify({"data": f"False"}), 200
    db_bot_config = ChromaDbConfig(collection_name=bot_id, dir="/db/")
    db = ChromaDB(config=db_bot_config)
    app_config = AppConfig(collect_metrics=False)
    new_bot = App(config=app_config, db=db)
    chat_bots[bot_id] = new_bot
    
    # serialize bot
    new_bot.save_to_file("/db/bots/"+bot_id)

    # return jsonify({"data": f"bot {bot_id} created"}), 200
    return jsonify({"data": f"True"}), 200

@app.route("/check_bot", methods=["POST"])
def check_bot():
    data = request.get_json()
    bot_id = data.get("bot_id", {})
    if len(bot_id) < 1:
        return jsonify({"error": "Invalid request. Please provide a valid bot_id."}), 400
    
    return jsonify({"data": f"{bool(bot_id in chat_bots)}"}), 200


@app.route("/add", methods=["POST"])
def add():
    data = request.get_json()
    bot_id = data.get("bot_id", {})
    chat_bot:App = None
    if len(bot_id) >= 1:
        if bot_id in chat_bots:
            chat_bot = chat_bots.get(bot_id)
        else:
            return jsonify({"error": "Invalid request. The bot_id provided does not exist."}), 400
    else:
        return jsonify({"error": "Invalid request. Please provide a valid bot_id."}), 400


    #app.logger.debug(data)
    data_type = data.get("data_type")        
    source = data.get("source")

    if data_type == "qna_pair":
        question = source.get("question",{})
        answer = source.get("answer",{})
        if len(question)>1 and len(answer)>1:
            source = (question, answer)
        else:
            return jsonify({"error": f"Failed to add qna_pair: make sure to add answer and question fields properly"}), 400

     # `source_id` is the hash of the source argument
    hash_object = hashlib.md5(str(source).encode("utf-8"))
    source_id = hash_object.hexdigest()

    if not source_id in hash_source_dict:
        hash_source_dict[source_id] = source

    #chunk_configuration
    chunck_size = data.get("config", {}).get("chunker", {}).get("chunk_size", 2048)
    chunck_overlap = data.get("config", {}).get("chunker", {}).get("chunk_overlap", 20)
    chunck_len = data.get("config", {}).get("chunker", {}).get("length_function", len)
    chunker_config = ChunkerConfig(chunk_size=chunck_size, chunk_overlap=chunck_overlap, length_function=chunck_len)
    #chunker_config = ChunkerConfig(chunk_size=2048, chunk_overlap=20, length_function=len)
    add_config = AddConfig(chunker=chunker_config)

    if data_type and source:
        try:
            doc_id = chat_bot.add(source=source, data_type=data_type, config=add_config)
            # rewrite bot 
            os.remove("/db/bots/"+bot_id)
            chat_bot.save_to_file("/db/bots/"+bot_id)
            # reserialize dictionary document
            with open('/db/dict/hash_source_dict.json', 'w') as json_file:
                json_string = json.dumps(hash_source_dict)
                json_file.write(json_string)
            return jsonify({"data": f"{doc_id}"}), 200
        except Exception as e:
            exception_info = traceback.format_exc()
            app.logger.debug(f'An exception occurred: {exception_info}')
            app.logger.debug(e)
            return jsonify({"error": f"Failed to add to {bot_id} {data_type}: {source}"}), 500
    return jsonify({"error": "Invalid request. Please provide 'data_type' and 'source' in JSON format."}), 400


@app.route("/query", methods=["POST"])
def query():
    data = request.get_json()

    data = request.get_json()
    bot_id = data.get("bot_id", {})
    chat_bot:App = None
    if len(bot_id) >= 1:
        if bot_id in chat_bots:
            chat_bot = chat_bots.get(bot_id)
        else:
            return jsonify({"error": "Invalid request. The bot_id provided does not exist."}), 400
    else:
        return jsonify({"error": "Invalid request. Please provide a valid bot_id."}), 400


    question = data.get("question")

    app.logger.info(hash_source_dict)
    

    #llm_configigurations
    number_documents = data.get("config", {}).get("llm_config", {}).get("number_documents", 5)
    max_tokens = data.get("config", {}).get("llm_config", {}).get("max_tokens", 100)
    chat_template = data.get("config", {}).get("llm_config", {}).get("chat_template")
    system_prompt = data.get("config", {}).get("llm_config", {}).get("system_prompt")
    temperature = data.get("config", {}).get("llm_config", {}).get("temperature", 0)
    top_p = data.get("config", {}).get("llm_config", {}).get("top_p", 1)
    dry_run = data.get("config", {}).get("dry_run", "False")
    
    bsc_chat_template = Template(chat_template)
    app.logger.debug(chat_template)
    app.logger.debug(system_prompt)
    app.logger.debug(number_documents)
    app.logger.debug(max_tokens)
    app.logger.debug(temperature)
    app.logger.debug(top_p)
    app.logger.debug(dry_run)
    
    llm_config = BaseLlmConfig(number_documents=number_documents, 
                           max_tokens=max_tokens,
                           template=bsc_chat_template, 
                           system_prompt=system_prompt,
                           top_p=top_p,
                           temperature=temperature
                           )

    llm_config.number_documents
    
    #aggiunta per filtrare su documento
    document = data.get("document", None)
    document_hash=None
    if document:
        document = get_key_from_value(hash_source_dict, document)
        document_hash = {"hash":f"{document}"}
    if question:
        try:
            response = chat_bot.query(input_query=question, config=llm_config, dry_run=ast.literal_eval(dry_run), where=document_hash)
            app.logger.debug(response)
            source_url = ""
            context = ""
            sep = ""
            if "{" in response:
                sep = "{"
            elif "<" in response:
                sep = "<"
            if sep != "":
                context = response.rsplit(sep,1)[-1][:-1]
                source_hash = chat_bot.db.collection.query(
                    query_texts=[
                        context,
                    ],
                    n_results=1,
                    where=document_hash, #aggiunta per filtrare su documento
                ).get('metadatas',{})[0][0].get("hash",{})
                source_url = hash_source_dict.get(source_hash, {})
                response = response.rsplit(sep,1)[0]

            return jsonify({"data": response, "source": source_url, "context": context}), 200
        except Exception as e:
            exception_info = traceback.format_exc()
            app.logger.debug(f'An exception occurred: {exception_info}')
            app.logger.debug(e)
            return jsonify({"error": "An error occurred. Please try again!"}), 500
    return jsonify({"error": "Invalid request. Please provide 'question' in JSON format."}), 400


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    question = data.get("question")
    if question:
        try:
            response = "chat_bots.chat(question)"
            return jsonify({"data": response}), 200
        except Exception:
            return jsonify({"error": "An error occurred. Please try again!"}), 500
    return jsonify({"error": "Invalid request. Please provide 'question' in JSON format."}), 400


if __name__ == "__main__":
    initialize_chat_bot()
    app.run(host="0.0.0.0", port=5000, debug=True)
