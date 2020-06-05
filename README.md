# Trivia Bot Thing
Requires Python 3.8+
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
