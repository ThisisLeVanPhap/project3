FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /workspace/multitenant

COPY multitenant/pom.xml pom.xml
COPY multitenant/.mvn .mvn
COPY multitenant/mvnw mvnw
COPY multitenant/src src

RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre-jammy

ARG INSTALL_LOCAL_AI=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/app

COPY chatbot/requirements-docker-base.txt /tmp/chatbot-requirements-docker-base.txt
RUN python3 -m pip install --no-cache-dir --retries 10 -r /tmp/chatbot-requirements-docker-base.txt

COPY chatbot/requirements-docker.txt /tmp/chatbot-requirements-docker.txt
RUN if [ "$INSTALL_LOCAL_AI" = "true" ]; then \
        python3 -m pip install --no-cache-dir --retries 10 -r /tmp/chatbot-requirements-docker.txt; \
    fi

COPY data_pipeline /opt/app/data_pipeline
COPY --from=build /workspace/multitenant/target/*.jar /opt/app/app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/opt/app/app.jar"]
