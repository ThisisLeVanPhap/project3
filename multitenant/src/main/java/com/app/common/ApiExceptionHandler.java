package com.app.common;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestControllerAdvice
public class ApiExceptionHandler {

    @ExceptionHandler(IllegalArgumentException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Map<String,Object> illegalArgs(IllegalArgumentException e) {
        return Map.of("error", "BadRequest", "message", e.getMessage());
    }

    @ExceptionHandler(IllegalStateException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Map<String,Object> illegalState(IllegalStateException e) {
        return Map.of("error", "BadRequest", "message", e.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Map<String,Object> beanValidation(MethodArgumentNotValidException e) {
        var field = e.getBindingResult().getFieldError();
        String msg = (field != null) ? (field.getField() + " " + field.getDefaultMessage()) : "Validation error";
        return Map.of("error", "ValidationError", "message", msg);
    }
}
