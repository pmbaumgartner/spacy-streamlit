FROM python:3.9

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt
RUN python -m spacy download en_core_web_sm
RUN pip install -e .

WORKDIR /app/examples
CMD ["streamlit", "run", "01_out-of-the-box.py", "--server.port", "8989", "--server.headless", "true"]