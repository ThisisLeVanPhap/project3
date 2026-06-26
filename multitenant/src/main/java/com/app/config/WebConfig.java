package com.app.config;

import com.app.tenant.TenantResolver;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.web.servlet.config.annotation.AsyncSupportConfigurer;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.concurrent.Executor;

@Configuration
@EnableAsync
@RequiredArgsConstructor
public class WebConfig implements WebMvcConfigurer {
    private final TenantResolver resolver;

    @Bean("crawlMaterializeExecutor")
    public Executor crawlMaterializeExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(1);
        executor.setMaxPoolSize(2);
        executor.setQueueCapacity(10);
        executor.setThreadNamePrefix("crawl-materialize-");
        executor.initialize();
        return executor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(resolver)
                .addPathPatterns("/api/**")

                .excludePathPatterns(
                        "/api/me",
                        "/api/onboarding-requests/**",
                        "/api/admin/tenants/**",
                        "/api/runtime/**",
                        "/actuator/**",
                        "/api/general/**",
                        "/api/internal/**");
    }
}
