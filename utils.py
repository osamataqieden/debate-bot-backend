import json
import os
from typing import BinaryIO 
import shutil


def structred_output_parser(output: str) -> dict:
    result = {}
    try:
        if '```json' in output:
            output = output.replace("```json","")
        if "```" in output:
            output = output.replace("```","")
        if output.startswith('"') or output.endswith('"'):
            output = output.replace('"',"")
        result = json.loads(output)
        return result
    except Exception as ext:
        print(str(ext))
        result = {}
    return output

def get_ext(file_name:str) -> str:
    try:
        return file_name.split(".")[-1]
    except Exception as ext:
        print(str(ext))
        return ""

def create_folder_if_not_exists(folder_name: str) -> bool:
    if os.path.exists(f"./{folder_name}"):
        return True
    try:
        os.mkdir(f"./{folder_name}")
        return True
    except:
        return False
    
def save_file_to_folder(file_path_with_name: str, bytes: BinaryIO) -> bool:
    try:
        with open(file_path_with_name,"wb") as file:
            shutil.copyfileobj(bytes, file)
        return True
    except Exception as ext:
        print(str(ext))
        return False