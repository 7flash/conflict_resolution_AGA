import os
import asyncio
import random
from datetime import datetime

import openai
import chainlit as cl
from kerykeion import AstrologicalSubject

import json

# Set the API key and model
openai.api_key = os.environ.get("OPENAI_API_KEY")
model_name = "gpt-3.5-turbo"
settings = {
    "temperature": 0.3,
    "max_tokens": 500,
    "top_p": 1,
    "frequency_penalty": 0,
    "presence_penalty": 0,
}

DATE_FORMAT = "%d/%m/%Y"
TIME_FORMAT = "%I:%M %p"

# Validation functions
def validate_date(date_string):
    try:
        datetime.strptime(date_string, DATE_FORMAT)
        return True
    except ValueError:
        return False

def validate_time(time_string):
    try:
        datetime.strptime(time_string, TIME_FORMAT)
        return True
    except ValueError:
        return False

def validate_place(place_string):
    return bool(place_string and place_string.strip())

PLANETS = [
    {"name": "Sun", "image": "https://upload.wikimedia.org/wikipedia/commons/e/e1/Sun_poster.svg"},
    {"name": "Moon", "image": "https://upload.wikimedia.org/wikipedia/commons/6/68/FullMoon2010.jpg"},
    {"name": "Mercury", "image": "https://upload.wikimedia.org/wikipedia/commons/d/d9/Mercury_in_color_-_Prockter07_centered.jpg"},
    {"name": "Venus", "image": "https://upload.wikimedia.org/wikipedia/commons/e/ef/Venus-real_color.jpg"},
    {"name": "Mars", "image": "https://upload.wikimedia.org/wikipedia/commons/4/4e/Mars_Valles_Marineris.jpeg"},
    {"name": "Jupiter", "image": "https://upload.wikimedia.org/wikipedia/commons/5/5a/Jupiter_and_its_shrunken_Great_Red_Spot.jpg"},
    {"name": "Saturn", "image": "https://upload.wikimedia.org/wikipedia/commons/c/c7/Saturn_during_Equinox.jpg"},
    {"name": "Uranus", "image": "https://upload.wikimedia.org/wikipedia/commons/3/3d/Uranus2.jpg"},
    {"name": "Neptune", "image": "https://upload.wikimedia.org/wikipedia/commons/5/56/Neptune_Full.jpg"},
    {"name": "Pluto", "image": "https://upload.wikimedia.org/wikipedia/commons/e/ef/Pluto_by_LORRI_and_Ralph%2C_13_July_2015.jpg"}
]

TESTING = True

async def validate_input(prompt, validation_func):
    """Utility function for validating user input"""
    while True:
        res = await cl.AskUserMessage(content=prompt).send()
        data = res["content"]
        if validation_func(data):
            return data
        await cl.AskUserMessage(content="Invalid input. Please try again.").send()

@cl.on_chat_start
async def start_chat():
    # Setting the initial message history for the user's session.
    initial_message = {
        "role": "system",
        "content": "You're entering a conversation with the celestial bodies of our solar system. Please ask them any question or advice you seek."
    }
    cl.user_session.set("message_history", [initial_message])
    
    # Sending an avatar for each planet.
    for planet in PLANETS:
        planet_name = planet["name"]
        planet_image_url = planet["image"]
        await cl.Avatar(name=planet_name, url=planet_image_url).send()
        
async def answer_as(name, chart):
    # Retrieve the message history from the user's session.
    message_history = cl.user_session.get("message_history")
    
    # Create an initial empty message.
    msg = cl.Message(author=name, content="")
    
    # Get the sun details from the chart.
    
    sun_name = chart["name"]
    sun_quality = chart["quality"]
    sun_element = chart["element"]
    sun_sign = chart["sign"]
    sun_position = chart["position"]
    sun_house = chart["house"]
    retrograde_status = "retrograde" if chart["retrograde"] else "direct"
    
    message_content = (
        f"speak as {name}. I am the {sun_name}, with the quality {sun_quality} and element {sun_element}. "
        f"Currently, I am in the sign of {sun_sign} at position {sun_position}. "
        f"I am in the {sun_house} house and moving in a {retrograde_status} motion."
    )

    # Make an API call to OpenAI's model for completion.
    async for stream_resp in await openai.ChatCompletion.acreate(
        model=model_name,
        messages=message_history + [{"role": "user", "content": message_content}],
        stream=True,
        **settings,
    ):
        token = stream_resp.choices[0]["delta"].get("content", "")
        await msg.stream_token(token)
    
    # Append the generated message to the message history and send it.
    message_history.append({"role": "assistant", "content": msg.content})
    await msg.send()

@cl.on_message
async def main(message: str):
    if message.lower().startswith("create my chart"):
        if TESTING:
            birth_data = {
                "date": "12/04/1998",
                "time": "08:20",
                "place": "Simferopol"
            }
            cl.user_session.set("birth_data", birth_data)
        else:
            # Prompt the user for birth data
            birth_date = await validate_input("What's your birth date? (e.g. DD/MM/YYYY)", validate_date)
            birth_time = await validate_input("What's your birth time? (e.g. HH:MM AM/PM)", validate_time)
            birth_place = await validate_input("Where were you born? (City, Country)", validate_place)
            
            birth_data = {
                "date": birth_date,
                "time": birth_time,
                "place": birth_place
            }
            cl.user_session.set("birth_data", birth_data)

        date_of_birth = birth_data["date"]
        time_of_birth = birth_data["time"]
        place_of_birth = birth_data["place"]

        astrological_subject = AstrologicalSubject(
            day=int(date_of_birth.split('/')[0]),
            month=int(date_of_birth.split('/')[1]),
            year=int(date_of_birth.split('/')[2]),
            hour=int(time_of_birth.split(':')[0]),
            minute=int(time_of_birth.split(':')[1]),
            city=place_of_birth
        )

        user_chart = astrological_subject.json()
        await cl.Message(content="Your astrological birth chart has been created! Here are the details: " + user_chart).send()

        # Store the user's chart in the session for subsequent queries
        cl.user_session.set("user_chart", user_chart)

    # Retrieve and update the message history
    message_history = cl.user_session.get("message_history")
    message_history.append({"role": "user", "content": message})

    user_chart = cl.user_session.get("user_chart")
    if isinstance(user_chart, str):
        user_chart = json.loads(user_chart)
    
    random_planets = random.sample([planet["name"] for planet in PLANETS], 2)
    tasks = []

    for planet in random_planets:
        try:
            chart_data = user_chart[planet.lower()]
            tasks.append(answer_as(planet, chart_data))
        except KeyError:
            print(f"{planet} data not found in user chart.")

    if tasks:
        await asyncio.gather(*tasks)