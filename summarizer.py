import json
import os
import requests

from bottle import request, response, route, run

from sumy.parsers.plaintext import PlaintextParser
from sumy.parsers.html import HtmlParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer as Summarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

LANGUAGE="english"
SENTENCES_COUNT="4"
PASSWORD = os.getenv("SUMMARIZER_PASSWORD")
USERNAME = os.getenv("SUMMARIZER_USERNAME")
SITENAME = os.getenv("SUMMARIZER_SITENAME")
SECRET_TOKEN = os.getenv("SUMMARIZER_SECRET")

if PASSWORD is None or USERNAME is None:
    print("Set SUMMARIZER_USERNAME and SUMMARIZER_PASSWORD in the environment.")
    exit(1)

if SITENAME is None:
    print("Set SUMMARIZER_SITENAME in the environment to your Rocket Chat instance's domain name.")
    exit(1)

if SECRET_TOKEN is None:
    print("Set SUMMARIZER_TOKEN in the environment to the token in the Rocket Chat Outgoing Integration that corresponds to this bot.")
    exit(1)


API_URL = "https://" + SITENAME + "/api/v1/"

def main():
    run(host='localhost', port=8080)

@route('/', method='post')
def summarize():
    response.content_type = "application/json"
    incoming = request.json
    if incoming.get('token', None) != SECRET_TOKEN:
        return

    channel = incoming.get('channel_id', None)
    if channel is None:
        return

    query = incoming.get('text', '').replace('!tldr', '').strip()
    count = 150
    if query != "":
        try:
            count = int(query) if int(query) > 10 and int(query) < 1000 else count
        except ValueError:
            pass

    r = requests.post(API_URL + "login",
                    data=json.dumps({"username": USERNAME,
                                     "password": PASSWORD}),
                    headers={"Content-type": "application/json"})

    try:
        user = r.json()
    except Exception as e:
        print("BAILING OUT (login):\n{}".format(e))
        return

    userdata = user.get('data', None)
    if userdata is None:
        print("Login failed")
        return

    uid = userdata.get('userId', None)
    authToken = userdata.get('authToken', None)

    if uid is None or authToken is None:
        print("uid or token was invalid")
        return

    r = requests.get(API_URL + \
                     "channels.history?roomId={}&count={}".format(channel, count),
                    headers={"X-Auth-Token": authToken,
                             "X-User-Id": uid})

    try:
        history = r.json()
    except Exception as e:
        print("BAILING OUT (history):\n{}".format(e))
        return

    last = history['messages'][1] # 0 is !tldr
    if last.get('urls', []) != []:
        summaries = []
        for url in last['urls']:
            parser = HtmlParser.from_url(url['url'], Tokenizer(LANGUAGE))
            stemmer = Stemmer(LANGUAGE)
            summarizer = Summarizer(stemmer)
            summarizer.stop_words = get_stop_words(LANGUAGE)
            summaries.append(
                "> {}".format(" ".join([str(sentence)\
                 for sentence in summarizer(parser.document,
                                            SENTENCES_COUNT)])))
        output = json.dumps({"text": "\n--\n".join(summaries)})
        return output

    messages = ". ".join(
        [m['msg'] for m in history['messages'][::-1] \
         if m['msg'] != "" and m.get('bot', None) is None])

    parser = PlaintextParser.from_string(messages, Tokenizer(LANGUAGE))
    stemmer = Stemmer(LANGUAGE)
    summarizer = Summarizer(stemmer)
    summarizer.stop_words = get_stop_words(LANGUAGE)

    return json.dumps(
        { "text": "\n--\n".join(
            ["> {}".format(str(sentence))
                 for sentence in summarizer(parser.document, SENTENCES_COUNT)])
        })

if __name__ == "__main__":
    main()
