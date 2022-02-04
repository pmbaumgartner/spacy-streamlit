import os
import sys
import re
import pytest
import spacy
from playwright.sync_api import Page, expect

MULTILINE_INPUT_KEY = "Meta" if sys.platform == "darwin" else "Control"


@pytest.mark.only_browser("chromium")
def test_out_of_the_box(page: Page):
    test_text = "David Robert Jones was born on 8 January 1947 in Brixton, London."
    model = "en_core_web_sm"
    nlp = spacy.load(model)
    doc = nlp(test_text)

    STREAMLIT_SERVER_PORT = os.environ.get("STREAMLIT_SERVER_PORT", "8501")

    page.goto(f"http://localhost:{STREAMLIT_SERVER_PORT}")

    # MODEL SELECTION
    # even though the `en_core_web_sm` model is selected by default
    # this selects it from the dropdown to confirm
    # yes, this is a wacky selector
    page.click("text=en_core_web_smopen >> div")

    # select model from list
    page.click(f'li[role="option"]:has-text("{model}")')

    # NEW TEXT IN TEXT AREA
    # This locates an element with the class `stTextArea`,
    # which has text containing 'Text to analyze' within it (from the label)
    # Then we select the textarea element that's a child of that
    input_text_element = page.locator(
        ".stTextArea:has-text('Text to analyze') >> textarea"
    )

    input_text_element.fill(test_text)
    input_text_element.press(f"{MULTILINE_INPUT_KEY}+Enter")

    # NER DISPLAY COMPONENT
    for ent in doc.ents:
        # make sure each entity is visible in the text display with its label
        # this isn't a very precise locator and we're using a regex
        # we could make this better with precise elements
        expect(page.locator(f"div.entities")).to_have_text(
            re.compile(rf"{ent.text}\s+{ent.label_}")
        )

    last_ent, last_ent_label = list([(ent.text, ent.label_) for ent in doc.ents])[-1]

    # ENTITY LABEL SELECTION
    entity_label_accordion = page.locator("text=Select entity labels")
    entity_label_accordion.click()  # expands

    # Deselect an ent type that is in the sentence - the x is an svg element
    page.locator(
        f"span[aria-label='{last_ent_label}, close by backspace']:has-text('{last_ent_label}')"
        " >> "
        "svg"
    ).click()
    # verify entity is no longer labeled
    expect(page.locator("div.entities")).not_to_have_text(
        re.compile(rf"{last_ent}\s+{last_ent_label}")
    )
