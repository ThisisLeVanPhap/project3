package com.app.config;

import com.app.tenant.TenantResolver;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
@RequiredArgsConstructor
public class WebConfig implements WebMvcConfigurer {
    private final TenantResolver resolver;

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(resolver)
                .addPathPatterns("/api/**")
                .excludePathPatterns("/api/admin/tenants/**", "/actuator/**");
    }
}
