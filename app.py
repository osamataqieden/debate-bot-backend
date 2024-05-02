from fastapi import FastAPI, HTTPException, File, UploadFile
import API_KEYS
from google import generativeai as genai
from data_objects import rejected_topics
from typing import Union
from utils import structred_output_parser, create_folder_if_not_exists,get_ext,save_file_to_folder
import json
import uuid
from fastapi.middleware.cors import CORSMiddleware

user_dict = {}
genai.configure(api_key=API_KEYS.GEMINI_KEY)
safety_settings = [
    {
        "category": "HARM_CATEGORY_DANGEROUS",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE",
    },
]



app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/debate/get_possible_topics")
def get_available_topics():
    prompt = '''Provide 3 debate topics as a JSON array, sticking with the following JSON format: 
    '{ 'topicTitle': str, 'topicDesc': str, 'topicDifficulty': str}', don't start the response with ```json and 
    don't add new lines or escape characters and don't end the response with a new line, also we need to use double quotes whenever possible and don't use markdown'''
    model = genai.GenerativeModel(model_name="models/gemini-1.5-pro-latest",safety_settings=safety_settings)
    new_topics = model.generate_content([prompt])
    result = new_topics.text.replace("\\n","")
    ser_result = structred_output_parser(result)
    return ser_result

@app.post("/debate/select_topic")
def select_topic(topic_selected: str):
    user_session = uuid.uuid4()
    user_data = {
        "user_session": str(user_session),
        "topic_selected": topic_selected,
        "is_started": False,
        "is_against": 0,
        "conversation": [],
        "responses": []
    }
    user_dict[str(user_session)] = user_data
    print(user_dict)
    return {
        "session_key": user_session
    }

@app.post("/debate/start_session")
def start_session(session_key: str, position: int):
    if session_key not in user_dict:
        raise HTTPException(status_code=404, detail="Session Key Not Found")
    user_dict[session_key]["is_started"] = True
    user_dict[session_key]["is_against"] = position
    return user_dict[session_key]

@app.post("/debate/session/submit_audio_and_get_response")
def submit_audio_and_get_response(session_key: str, audio_file: UploadFile):
    if session_key not in user_dict:
        raise HTTPException(status_code=404, detail="Session Key Not Found")
    user_session = user_dict[session_key]
    if create_folder_if_not_exists(session_key) is False:
        raise HTTPException(status_code=500, detail="Unknown Filehandlig Error")
    file_assigned_uid = uuid.uuid4()
    create_folder_if_not_exists(f"{session_key}/{str(file_assigned_uid)}")
    file_path = f"{session_key}/{str(file_assigned_uid)}/{str(file_assigned_uid)}.{get_ext(audio_file.filename)}"
    if save_file_to_folder(file_path, audio_file.file) == False:
        raise HTTPException(status_code=500, detail="Unknown Filehandlig Error")
    prompt = '''You are debating a human, the voice sent with this prompt is their response to a point you made earlier,
        respond with the following:
        - Your response to the their point. (be brutal and don't provide positive feedback)
        - Your rateing of their point in relation to the debate topic. (be comprehansive and brutal) 
        - Your evaluation of their tone, confidance, articulation (also be brutal) 
        - Transcription of their argument
        Your response should conform to the below JSON template:
        "{"Response": Your Response,"ArguementRating": Your rating of their arguement as specified above,"ArgumentRatingNumerical": Your rating of their arguement as specified above from 1 to 10,"ToneRating": Your rating of their their tone as specified above,"ToneRatingNumerical": Your rating of speaking skills from 1 to 10,"ArgumentText": Transcription of their argument}"'''
    if user_session["is_against"] == 0:
        prompt = prompt + f'''
        The topic is {user_session["topic_selected"]}, you are taking the affrimative position.  
        '''
    else:
        prompt = prompt + f'''
            The topic is {user_session["topic_selected"]}, you are taking the against position.  
        '''
    if len(user_session["conversation"]) > 0:
        prompt = prompt + "The below is the history of your conversation"
        for conv in user_session["conversation"]:
            if conv["type"] == "user":
                prompt += f'USER: {conv["text"]}\\n'
            else:
                prompt += f'SYSTEM: {conv["text"]}\\n'
    prompt = prompt + "\\n , don't start the response with ```json and don't add new lines or escape characters and don't end the response with a new line, also we need to use double quotes whenever possible and don't use markdown"
    response = genai.upload_file(path=file_path,display_name=f"{str(file_assigned_uid)}.{get_ext(audio_file.filename)}")
    model = genai.GenerativeModel(model_name="models/gemini-1.5-pro-latest", safety_settings=safety_settings)
    query_response = model.generate_content([prompt, response])
    dict_response = structred_output_parser(query_response.text.replace("\n",""))
    print(dict_response)
    if dict_response is str:
        print(dict_response)
        raise HTTPException(status_code=500, detail="Failed to parse JSON")

    user_session["conversation"].append({
        "type": "user",
        "text": dict_response["ArgumentText"]
    })
    user_session["conversation"].append({
        "type": "system",
        "text": dict_response["Response"]
    })
    user_session["responses"].append(dict_response)
    return dict_response

@app.post("/debate/finish_session")
def finish_session(session_key:str):
    if session_key not in user_dict:
        raise HTTPException(status_code=404, detail="Session Key Not Found")
    user_session = user_dict[session_key]
    prompt = "You were debating a person on the topic below,"
    if user_session["is_against"] == 0:
        prompt = prompt + f'''The topic is {user_session["topic_selected"]}, you are taking the affrimative position.'''
    else:
        prompt = prompt + f'''The topic is {user_session["topic_selected"]}, you are taking the against position.'''
    prompt = prompt + '''
        The conversion history is as below as a JSON string, the JSON field's description is as below:
        "{"Response": Your Response,"ArguementRating": Your rating of their arguement as specified above,"ArgumentRatingNumerical": Your rating of their arguement as specified above from 1 to 10,"ToneRating": Your rating of their their tone as specified above,"ToneRatingNumerical": Your rating of speaking skills from 1 to 10,"ArgumentText": Transcription of their argument}"
    '''
    for response in user_session["responses"]:
        prompt = prompt + str(response) + "\n"
    prompt = prompt + '''
        You are to rate the strength of their argument, their overall articulation and confidance, and overall in a numerical fashion, every numurical rating is on a scale of 1 - 10, also you should give them tips for improvements.
        You are to give them as below JSON:
        "{"ArgumentStrengthRatingNumerical": number,"ArgumentStrengthRatingDescription": string,"ArgumentSpeakingRatingNumerical": number,"ArgumentSpeakingRatingDescription": string,"TipsForImprovement": string, "OverallRating": number}"
    '''
    prompt = prompt + "\\n , don't start the response with ```json and don't add new lines or escape characters and don't end the response with a new line, also we need to use double quotes whenever possible and don't use markdown"
    print (prompt)
    model = genai.GenerativeModel(model_name="models/gemini-1.5-pro-latest",safety_settings=safety_settings)
    query_response = model.generate_content([prompt])
    dict_response = structred_output_parser(query_response.text.replace("\n",""))
    if dict_response is str:
        print(dict_response)
        raise HTTPException(status_code=500, detail="Failed to parse JSON")
    dict_response["user_session"] = user_session
    return dict_response




