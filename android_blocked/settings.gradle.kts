pluginManagement {
    repositories {
        // 使用阿里云镜像加速插件下载
        maven { url = uri("https://maven.aliyun.com/repository/google") }
        maven { url = uri("https://maven.aliyun.com/repository/public") }
        maven { url = uri("https://maven.aliyun.com/repository/gradle-plugin") }
        google()          // 保留，兜底
        mavenCentral()    // 保留，兜底
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        // 依赖也优先走阿里云
        maven { url = uri("https://maven.aliyun.com/repository/google") }
        maven { url = uri("https://maven.aliyun.com/repository/public") }
        google()          // 兜底
        mavenCentral()    // 兜底
    }
}

rootProject.name = "ClassroomIoT"
include(":app")
