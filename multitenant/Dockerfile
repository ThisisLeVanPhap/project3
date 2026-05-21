FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /workspace/multitenant

COPY multitenant/pom.xml pom.xml
COPY multitenant/.mvn .mvn
COPY multitenant/mvnw mvnw
COPY multitenant/src src

RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre-jammy

WORKDIR /opt/app

COPY --from=build /workspace/multitenant/target/*.jar /opt/app/app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/opt/app/app.jar"]
