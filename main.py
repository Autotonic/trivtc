# TODO probably has a couple broken bits, fix em
import asyncio
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, List, NoReturn, Optional, Union

import requests
import ujson
import websockets

from python_anticaptcha import (AnticaptchaClient, AnticatpchaException,
                                NoCaptchaTaskProxylessTask)


@dataclass
class Client:
    anticaptcha: str
    nickname: str
    password: str
    roomname: str
    session: str
    username: str
    prefix: str
    headers: dict


@dataclass
class User:
    achievement_url: str
    avatar: str
    featured: bool
    giftpoints: int
    handle: int
    lurker: bool
    mod: bool
    nick: str
    owner: bool
    session_id: str
    subscription: int
    username: str

    def __post_init__(self):
        self.join_time = datetime.now()


@dataclass
class Room:
    avatar: str
    biography: str
    giftpoints: int
    location: str
    msg_constraints: int
    name: str
    pushtotalk: bool
    recent_gifts: list
    session_timeout_for_guests: int
    subscription: int
    topic: str
    type: str
    website: str
    youtube_enabled: bool
    users: List[User] = field(default_factory=list)

    def __add__(self, user: User) -> NoReturn:
        self.users.append(user)

    def __sub__(self, handle: int) -> NoReturn:
        user = self.get_by_handle(handle)
        for i, _user in enumerate(self.users):
            if _user == user:
                del self.users[i]
                break

    def __userloop(self, argument, attribute) -> Optional[User]:
        for user in self.users:
            if user.__getattribute__(attribute) == argument:
                return user

    @property
    def usercount(self):
        return len(users)

    @property
    def nicks(self):
        return [user.nick for user in self.users]

    @property
    def mods(self):
        return [user for user in self.users if user.mod]

    @property
    def lurkers(self):
        return [user for user in self.users if user.lurker]

    def get_by_handle(self, handle: int) -> Optional[User]:
        return self.__userloop(handle, "handle")

    def get_by_nick(self, nickname: str) -> Optional[User]:
        return self.__userloop(nickname, "nick")

    def get_by_username(self, username: str) -> Optional[User]:
        return self.__userloop(username, "username")

    def set_nick(self, handle: int, newnick: str) -> NoReturn:
        user = self.get_by_handle(handle)
        if user:
            self.users[user].nick = newnick


@dataclass
class Message:
    user: User
    text: str

    def __post_init__(self):
        self.text: str = self.text.strip()


@dataclass
class Command:
    user: User
    raw: str
    prefix: str

    def __post_init__(self):
        parts = self.raw.split(" ")
        self.cmd: str = parts[0].lstrip(self.prefix)
        self.text: str = self.raw.lstrip(parts[0]).strip()


@dataclass
class Trivia:
    participants: List[User]
    question: str = field(default_factory=str)
    answer: str = field(default_factory=str)

    def __post_init__(self):
        self.start = time.time()


class Bot:
    def __init__(self, client: Client):
        self.client: Client = client
        self.bot: User = None
        self.session = client.session
        self.room: Room = None
        self.req = 0
        self.ws = None
        self.captcha_client = None
        if len(client.anticaptcha) > 1:
            self.captcha_client = AnticaptchaClient(client.anticaptcha)

        self.trivia: Trivia = None
        self.trivia_files = [each for each in Path("questions/").glob("*")]

    def get_req(self) -> int:
        self.req += 1
        return self.req

    async def wsend(self, message: dict) -> NoReturn:
        await self.ws.send(ujson.dumps(message))

    async def sendmsg(self, message: str) -> NoReturn:
        payload = {"tc": "msg", "req": self.get_req(), "text": message}
        await self.wsend(payload)

    async def do_captcha(self, key: str):
        try:
            task = NoCaptchaTaskProxylessTask(
                "https://tinychat.com/room/{}".format(self.client.roomname), key
            )
            job = self.captcha_client.createTask(task)
            job.join()
            print("Captcha complete")
            payload = {"tc": "captcha", "req": 1, "token": job.get_solution_response()}
            await self.wsend(payload)

        except AnticatpchaException as e:
            sys.exit(e)

    def rtc(self) -> Optional[str]:
        req = self.session.get(f"https://tinychat.com/room{self.client.roomname}")
        if req.status_code == 200:
            match = re.search(r"webrtc\/([0-9.-]+)\/", req.text)
            rtcversion = match[1]
            return rtcversion

    def csrf(self) -> Optional[str]:
        req = self.session.get(f"https://tinychat.com/start?")
        if req.status_code == 200:
            match = re.search('(?:csrf-token" content=")(\w+)', req.text)
            return match[1]

    def token(self) -> Optional[dict]:
        req = self.session.get(
            f"https://tinychat.com/api/v1.0/room/token/{self.client.roomname}"
        )
        if req.status_code == 200:
            return req.json()

    def login(self) -> Optional[str]:
        formdata = {
            "login_username": self.client.username,
            "login_password": self.client.password,
            "remember": "1",
            "next": "https://tinychat.com/room/" + self.client.roomname,
            "_token": self.csrf(),
        }
        log = self.session.post(
            url="https://tinychat.com/login", data=formdata, allow_redirects=True
        )
        if log.status_code == 200:
            if re.search("The password you specified is incorrect", log.text):
                sys.exit("Password is incorrect")
            elif re.search("That username is not registered", log.text):
                sys.exit("Username is incorrect")
        else:
            sys.exit(f"Couldn't login got: {log.status_code}")

    async def connect(self) -> NoReturn:
        self.login()
        token = self.token()
        rtc = self.rtc()
        payload = {
            "tc": "join",
            "req": self.req,
            "useragent": "tinychat-client-webrtc-chrome_linux x86_64-" + rtc,
            "token": token["result"],
            "room": self.client.roomname,
            "nick": self.client.nickname,
        }
        async with websockets.connect(
            uri=token["endpoint"],
            subprotocols=["tc"],
            extra_headers=self.client.headers,
            timeout=600,
            origin="https://tinychat.com",
        ) as self.ws:
            await self.wsend(payload)
            self.running = True
            async for message in self.ws:
                await self.consume(message)

    async def consume(self, message: str) -> NoReturn:
        message = ujson.loads(message)
        tc = message["tc"]
        if tc == "ping":
            ping = {"tc": "pong", "req": self.get_req()}
            await self.wsend(ping)
        elif tc == "password":
            sys.exit("Password not handled")
        elif tc == "captcha":
            if self.captcha_client:
                print("Doing the captcha")
                await self.do_captcha(message["key"])
            else:
                sys.exit("Got captcha")
        elif tc == "joined":
            self.room = Room(**message["room"])
            self.bot = User(**message["self"])
            print("Connected...")
        elif tc == "quit":
            self.room - message["handle"]
        elif tc == "join":
            # remove the "tc" so we can dump straight into the dataclass
            del message["tc"]
            user = User(**message)
            self.room + user
            print(f"{user.nick} ({user.username}) joined")
        elif tc == "userlist":
            for user in message["users"]:
                self.room + User(**user)
        elif tc == "nick":
            self.room.set_nick(message["handle"], message["nick"])
        elif tc == "msg":
            user = self.room.get_by_handle(message["handle"])
            msg = Message(user=user, text=message["text"])
            print(f"<{msg.user.nick}> {msg.text}")
            if message["text"].startswith(self.client.prefix) and user != self.bot:
                cmd = Command(user=user, prefix=self.client.prefix, raw=message["text"])
                await self.fire(cmd)
            elif self.trivia is not None and user in self.trivia.participants:
                print(f"[TRIVIA] {user.nick} is trying {msg.text}")
                answer = self.try_answer(msg)
                if answer:
                    await self.sendmsg(
                        f"{user.nick} is correct! Answer: {self.trivia.answer}"
                    )
                    await self.do_trivia(True)
                else:
                    await self.sendmsg(f"{user.nick} is incorrect!")

    async def fire(self, command: Command) -> NoReturn:
        if command.cmd == "start" and (command.user.mod | command.user.owner):
            if self.trivia is None:
                print("[TRIVIA] STARTING")
                await self.sendmsg(
                    f"Trivia has started! Use {self.client.prefix}join to participate!"
                )
                await self.do_trivia()

        elif command.cmd == "stop" and (command.user.mod | command.user.owner):
            if self.trivia is not None:
                print("[TRIVIA] STOP")
                self.trivia = None
                await self.sendmsg(f"{command.user.nick} has stopped trivia")

        elif command.cmd in ["skip", "next"] and (
            command.user.mod | command.user.owner
        ):
            await self.do_trivia(True)

        elif command.cmd == "join" and command.user.username != "":
            self.trivia.participants.append(command.user)
            print(f"[TRIVIA] Added {command.user}")
            print(f"[TRIVIA] Current participants: {self.trivia.participants}")

        elif command.cmd == "quit":
            self.trivia.participants.remove(command.user)

        elif command.cmd == "help":
            helpmsg = f"Prefix: {self.client.prefix}, Commands: skip/next to skip the question, quit to remove yourself from trivia, join to join"
            await self.sendmsg(helpmsg)

    async def do_trivia(self, is_next: Optional[bool] = False) -> NoReturn:
        question, answer = self.get_random_trivia()
        if self.trivia is not None:
            self.trivia.question = question
            self.trivia.answer = answer
        else:
            self.trivia = Trivia([], question=question, answer=answer)
        print(answer)
        msg = f"{question}"
        if is_next:
            msg = "𝗡𝗲𝘅𝘁 𝗤𝘂𝗲𝘀𝘁𝗶𝗼𝗻:\n" + msg
        await self.sendmsg(msg)

    def get_random_trivia(self) -> str:
        f = random.choice(self.trivia_files)
        line = None
        with f.open("r") as trivia_file:
            line = random.choice(trivia_file.readlines())
        parts = line.split("`")
        return (parts[0].strip(), parts[1])

    def try_answer(self, msg: Message) -> bool:
        maybe = SequenceMatcher(None, msg.text.lower(), self.trivia.answer.lower())
        # ratio is the most "accurate"
        print(f"ratio: {maybe.ratio()}")
        # quick ratio is a bit more aggressive but similar to ratio
        # for shorter strings
        print(f"quick: {maybe.quick_ratio()}")
        # most aggressive and will most likely match >0.8 if
        # the they have enough similar letters
        print(f"realq: {maybe.real_quick_ratio()}")
        # 0.85 seems like the most common with a character off
        # so we'll set it a touch below for people who really can't spell (me)
        if maybe.ratio() >= 0.8:
            return True


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.79 Safari/537.36 Edge/14.14393",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://tinychat.com",
}
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
bot = Bot(client)
asyncio.get_event_loop().run_until_complete(bot.connect())
