FROM tensorflow/tensorflow:2.4.0-gpu-jupyter

# ADD ./requirements.txt .

ENV PATH="/.local/bin:${PATH}"

RUN mkdir .cache
RUN apt-get update -y && apt-get install git wget python3.7 -y
RUN pip install nbdev pre-commit

EXPOSE 8888 6006
