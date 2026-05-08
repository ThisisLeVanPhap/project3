FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /workspace/multitenant

COPY multitenant/pom.xml pom.xml
COPY multitenant/.mvn .mvn
COPY multitenant/mvnw mvnw
COPY multitenant/src src

RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DEFAULT_TIMEOUT=600 \
    PYTHON_BIN=/usr/bin/python3 \
    MODEL_SERVER_DIR=/opt/app/chatbot

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/app

COPY chatbot /opt/app/chatbot
RUN python3 -m pip install --no-cache-dir --retries 10 -r /opt/app/chatbot/requirements-docker.txt

COPY --from=build /workspace/multitenant/target/*.jar /opt/app/app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/opt/app/app.jar"]
