import json

import os



CONFIG_FILE = "config.json"





def load_config():

    if not os.path.exists(CONFIG_FILE):

        default_config = {

            "ADMIN_ID": "ADMIN_ID",

            "BOT_TOKEN": "",

            "BOT_PASSWORD": "",

            "ADMINS": []

        }



        with open(CONFIG_FILE, "w", encoding="utf-8") as f:

            json.dump(default_config, f, ensure_ascii=False, indent=2)



        return default_config



    with open(CONFIG_FILE, "r", encoding="utf-8") as f:

        return json.load(f)





def save_config(data):

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:

        json.dump(data, f, ensure_ascii=False, indent=2)



def is_admin(user_id):

    config = load_config()

    return (

        user_id == config.get("ADMIN_ID")

        or user_id in config.get("ADMINS", [])


    )



