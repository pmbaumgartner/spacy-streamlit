import socket
import sys
from contextlib import closing
from subprocess import PIPE, Popen, TimeoutExpired
from time import sleep
from typing import Tuple
from warnings import warn
import signal
import os

import pytest
import spacy
from playwright.sync_api import Page

MULTILINE_INPUT_KEY = "Meta" if sys.platform == "darwin" else "Ctrl"


def find_free_port() -> int:
    # https://stackoverflow.com/a/45690594
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


@pytest.fixture
def streamlit_app(capsys):
    if os.environ.get("ENVIRONMENT") == "gha":
        # we're on github actions
        yield None, 8989
    else:
        # we're local
        free_port = find_free_port()
        stapp = Popen(
            [
                "streamlit",
                "run",
                "01_out-of-the-box.py",
                "--server.port",
                str(free_port),
                "--server.headless",
                "true",
            ],
            cwd="examples",
            stdout=PIPE,
            stderr=PIPE,
        )
        sleep(1)  # give the app some time to startup
        returncode = stapp.poll()
        if returncode is not None:
            with capsys.disabled():
                warn(stapp.stderr.peek().decode())
                pytest.fail("Failed to start Streamlit App")
        # no return code if app is running
        startup_loop = True
        retries = 30
        retry_counter = 0
        while startup_loop and retry_counter < retries:
            if (
                "You can now view your Streamlit app in your browser."
                in stapp.stdout.peek().decode()
            ):
                startup_loop = False
                yield stapp, free_port
            else:
                with capsys.disabled():
                    warn("Streamlit app not running yet. Waiting 1s.")
                sleep(1)
                returncode = stapp.poll()
                retry_counter += 1
                if returncode is not None:
                    with capsys.disabled():
                        warn(stapp.stderr.peek().decode())
                        pytest.fail(
                            f"Failed to start Streamlit App. Retries: {retries}"
                        )
        if retry_counter == retries:
            with capsys.disabled():
                warn(stapp.stderr.peek().decode())
                pytest.fail(f"Failed to start Streamlit App after {retries} retries.")
        try:
            stapp.send_signal(signal.SIGINT)
            stapp.wait(timeout=15)
        except TimeoutExpired:
            stapp.kill()
            stapp.terminate()


@pytest.mark.only_browser("chromium")
def test_out_of_the_box(streamlit_app: Tuple[Popen, int], page: Page):
    stapp_process, port = streamlit_app
    test_text = "David Robert Jones was born on 8 January 1947 in Brixton, London."
    model = "en_core_web_sm"
    nlp = spacy.load(model)
    doc = nlp(test_text)

    page.goto(f"http://localhost:{port}")

    # even though the `en_core_web_sm` model is default
    # this selects it from the dropdown to confirm
    # yes, this is a wacky selector
    page.click("text=en_core_web_smopen >> div")

    # select model from list
    page.click(f'li[role="option"]:has-text("{model}")')

    # This first locates an element with the class `stTextArea`,
    # which has text containing 'Text to analyze' within it (from the label)
    # Then we select the textarea element that's a child of that
    input_text_element = page.locator(
        ".stTextArea:has-text('Text to analyze') >> textarea"
    )

    input_text_element.fill(test_text)

    input_text_element.press(f"{MULTILINE_INPUT_KEY}+Enter")

    for ent in doc.ents:
        ent_text = f"{ent.text} {ent.label_}"
        # make sure each entity is visible in the display with its label
        page.locator(f"div.entities >> text={ent_text}").is_visible()

    entity_label_accordion = page.locator("text=Select entity labels")
    entity_label_accordion.click()  # expands
