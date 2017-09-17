import sys, json, requests
import datetime
import math
from flask import Flask, request
from mongoengine import *
connect('fastbot', host='localhost', port=27017)


try:
    import apiai
except ImportError:
    sys.path.append(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir)
    )
    import apiai

class User(Document):
    first_name = StringField(max_length=200)
    last_name = StringField(max_length=200)
    uid = IntField()
    age = IntField()
    height = IntField()
    gender = StringField()
    weight = IntField()
    tdee = IntField()

app = Flask(__name__)

PAT = 'EAACdwvY1FIoBAMx6zwJXKjJU02RSIZB8TdZA89xMZCbhOQKYvZCqNdX3xmNQp5TttLVAkWqxsbZBi0erA8aFpvHxzxcf9qK1BaTwpD4nxEGUTTh2rhWXZC6gBScqwhG7E8OCqebtrhXoNpNELLUIeHsFtgTBQFIBQUz1T21trOlAZDZD'

CLIENT_ACCESS_TOKEN = 'bb9c618e017f436aa0db1cb72b6614e2'

VERIFY_TOKEN = 'imfastingwithsumaya'

ai = apiai.ApiAI(CLIENT_ACCESS_TOKEN)


@app.route('/', methods=['GET'])
def handle_verification():
    '''
    Verifies facebook webhook subscription
    Successful when verify_token is same as token sent by facebook app
    '''
    if (request.args.get('hub.verify_token', '') == VERIFY_TOKEN):
        print("succefully verified")
        return request.args.get('hub.challenge', '')
    else:
        print("Wrong verification token!")
        return "Wrong validation token"


@app.route('/', methods=['POST'])
def handle_message():
    '''
    Handle messages sent by facebook messenger to the applicaiton
    '''
    data = request.get_json()

    try:
        if data["object"] == "page":
            for entry in data["entry"]:
                for messaging_event in entry["messaging"]:
                    if messaging_event.get("message"):
                        sender_id = messaging_event["sender"]["id"]
                        recipient_id = messaging_event["recipient"]["id"]
                        message_text = messaging_event["message"]["text"]
                        send_message(sender_id, parse_user_message(message_text, sender_id))
        return "ok"
    except:
        print('failed')
        return "ok"


def send_message(sender_id, message_text):
    '''
    Sending response back to the user using facebook graph API
    '''

    text = message_text["text"] or message_text
    quick_replies = message_text["quick_replies"] or []

    if len(quick_replies) > 0:
        r = requests.post("https://graph.facebook.com/v2.6/me/messages",

            params={"access_token": PAT},

            headers={"Content-Type": "application/json"},

            data=json.dumps({
            "recipient": {"id": sender_id},
            "message": {
                "text": text,
                "quick_replies": quick_replies,
            }
        }))
    else:
        r = requests.post("https://graph.facebook.com/v2.6/me/messages",

            params={"access_token": PAT},

            headers={"Content-Type": "application/json"},

            data=json.dumps({
            "recipient": {"id": sender_id},
            "message": {
                "text": text,
            }
        }))

def calculate_tdee(age, height, weight=150, gender='male'):
    weightFactor = 9.99
    heightFactor = 6.25
    ageFactor = 4.92
    result = ((weightFactor * weight) + (heightFactor * height) - (ageFactor * age))
    if gender == 'male':
        bmr = math.floor(result + 5)
    else:
        bmr = math.floor(result - 161)
    kcalpm = 9
    percentOfBMR = math.floor((7 * bmr) / 100)
    EPOC = percentOfBMR*1
    tea = math.floor((1 * 60 * kcalpm + EPOC) / 7)
    neat = 500
    total = bmr + tea + neat
    tef = math.floor(total/10)
    return total + tef

def parse_user_message(user_text, user_id):
    '''
    Send the message to API AI which invokes an intent
    and sends the response accordingly
    The bot response is appened with weaher data fetched from
    open weather map client
    '''

    request = ai.text_request()
    request.query = user_text

    response = json.loads(request.getresponse().read().decode('utf-8'))
    responseStatus = response['status']['code']
    result = response['result']
    action = result.get('action')
    if (responseStatus == 200):
        try:
            text = response['result']['fulfillment']['speech'].replace("\\n", "\n")
            quick_replies = []
            current_user = User.objects(uid = user_id)
            if action is not None:
                if action == "newsetup_name":
                    User.objects(uid=user_id).modify(upsert=True, new=True, set__first_name=result['parameters']['given-name'])
                elif action == "onboarding_height":
                    User.objects(uid=user_id).modify(upsert=True, new=True, set__height=result['parameters']['unit-length']['amount'])
                elif action == "onboarding_weight":
                    User.objects(uid=user_id).modify(upsert=True, new=True, set__weight=result['parameters']['given-name'])
                elif action == "onboarding_gender":
                    User.objects(uid=user_id).modify(upsert=True, new=True, set__gender=result['parameters']['number'])
                elif action == "onboarding_dob":
                    User.objects(uid=user_id).modify(upsert=True, new=True, set__age=2017 - int(result['parameters']['date'][0:4]))
                # elif action == tdee:
                #     User.objects(uid=user_id).modify(upsert=True, new=True, set__tdee=result['parameters']['given-name'])
                try:
                    temp = result['fulfillment']['messages']
                    for i in range(len(temp)):
                        try:
                            if temp[i]['type'] == 2:
                                options = result['fulfillment']['messages'][i]['replies']
                        except:
                            print('l')
                    options = options or []
                    if action == "onboarding_height":
                        text = text + " Your TDEE is: " + str(calculate_tdee(current_user[0].age, current_user[0].height))
                except:
                    options = []
                for option in options:
                    quick_replies += [{
                        "content_type": "text",
                        "title": option,
                        "payload": "<POSTBACK_PAYLOAD>",
                    }]

            return ({"text": text, "quick_replies": quick_replies})
        except:
            return (response['result']['fulfillment']['speech'])

    else:
        return ("Sorry, I couldn't understand that question")


def send_message_response(sender_id, message_text):

    sentenceDelimiter = ". "
    messages = message_text.split(sentenceDelimiter)

    for message in messages:
        send_message(sender_id, message + ". ")

if __name__ == '__main__':
    app.run()
