# syntax=docker/dockerfile:1

FROM nvidia/cuda:11.3.1-cudnn8-devel-ubuntu20.04

WORKDIR /home/app
COPY . .

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-pip libsndfile1-dev ffmpeg
RUN python3 -m pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu113
RUN python3 -m pip install -r requirements.txt

ENV DIR_LOGS=/logs
ENV DIR_DATA=/data
RUN mkdir -p $DIR_LOGS
RUN mkdir -p $DIR_DATA

ENV HYDRA_FULL_ERROR=1
