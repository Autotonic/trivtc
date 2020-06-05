# Trivia Bot Thing
Requires Python 3.8+

Questions were obtained from [triviabot](https://github.com/rawsonj/triviabot "triviabot")

### Running
- 1 `pipenv install`
- 2 Set the configuration in `main.py`
```py
client = Client(
    roomname="",
    username="",
    password="",
    nickname="TriviaBot",
    prefix="?",
    anticaptcha="",
    headers=headers,
    session=requests.Session(),
)
```
- 3 `pipenv run python main.py`

### Running without pipenv :(
Required packages:

```py
websockets = "*"
ujson = "*"
requests = "*"
python-anticaptcha = "*"
```
