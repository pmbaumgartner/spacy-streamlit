import os
import signal
import sys
from subprocess import PIPE, Popen, TimeoutExpired
from time import sleep
from typing import NewType, Optional
from warnings import warn

import pytest
import spacy
from playwright.sync_api import Page

MULTILINE_INPUT_KEY = "Meta" if sys.platform == "darwin" else "Control"

StreamlitPort = NewType("StreamlitPort", int)
StreamlitProcess = NewType("StreamlitProcess", Popen)

# This fixture is function scoped since the one test we have is linear and changes
# the state of the app. You might want another session scoped fixture if you're just
# checking for initial content on the page and _not_ interacting with it and changing state.
@pytest.fixture(scope="function")
def streamlit_app(capsys) -> StreamlitPort:
    port: StreamlitPort = 8989

    if os.environ.get("ENVIRONMENT") == "gha":
        # we're on github actions, the docker image is
        # running as a service already
        yield port
    else:
        # we're local
        stapp: StreamlitProcess = Popen(
            [
                "streamlit",
                "run",
                "01_out-of-the-box.py",
                "--server.port",
                str(port),
                "--server.headless",
                "true",
            ],
            cwd="examples",
            stdout=PIPE,
            stderr=PIPE,
        )
        sleep(1)  # give the app some time to startup
        returncode = stapp.poll()
        # no return code if app is running
        if returncode is not None:
            warn_stderr_and_fail(stapp, capsys)
        # app should be running
        startup_loop = True
        retries = 5
        retry_counter = 1
        while startup_loop and retry_counter <= retries:
            if (
                "You can now view your Streamlit app in your browser."
                in stapp.stdout.peek().decode()
            ):
                startup_loop = False
                yield port
            else:
                with capsys.disabled():
                    print("Streamlit app not running yet. Waiting 1s.")
                sleep(1)
                returncode = stapp.poll()
                retry_counter += 1
                if returncode is not None:
                    warn_stderr_and_fail(stapp, capsys, retries=retries)

        if retry_counter == retries:
            warn_stderr_and_fail(stapp, capsys, retries=retries)

        # cleanup
        try:
            stapp.send_signal(signal.SIGINT)
            stapp.wait(timeout=15)
        except TimeoutExpired:
            stapp.kill()
            stapp.wait(timeout=15)


def warn_stderr_and_fail(
    streamlit_process: StreamlitProcess, capsys, retries: Optional[int] = None
) -> None:
    with capsys.disabled():
        warn("\n" + streamlit_process.stderr.peek().decode())
        if not retries:
            pytest.fail(f"Failed to start Streamlit App")
        else:
            pytest.fail(f"Failed to start Streamlit App. Retries: {retries}.")


@pytest.mark.only_browser("chromium")
def test_out_of_the_box(page: Page):
    test_text = "David Robert Jones was born on 8 January 1947 in Brixton, London."
    model = "en_core_web_sm"
    nlp = spacy.load(model)
    doc = nlp(test_text)

    page.goto(f"http://localhost:8989")

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
