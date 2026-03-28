plugins {
    id("java-library")
}

java {
    sourceCompatibility = JavaVersion.VERSION_1_8
    targetCompatibility = JavaVersion.VERSION_1_8
}

// 配置默认 JAR 任务
tasks.jar {
    archiveBaseName.set("lxb-core")

    manifest {
        attributes(
            "Main-Class" to "com.lxb.server.Main",
            "Manifest-Version" to "1.0"
        )
    }
}

// 转换为 DEX 格式（Android 需要）
tasks.register<Exec>("dex") {
    dependsOn("jar")

    val jarFile = layout.buildDirectory.file("libs/lxb-core.jar")
    val outputDir = layout.buildDirectory.dir("libs")

    // 查找 Android SDK build-tools 中的 d8
    val androidHome = System.getenv("ANDROID_HOME")
        ?: System.getenv("ANDROID_SDK_ROOT")
        ?: "${System.getProperty("user.home")}/AppData/Local/Android/Sdk"

    val buildToolsDir = file("$androidHome/build-tools")
    val latestBuildTools = buildToolsDir.listFiles()
        ?.filter { it.isDirectory }
        ?.maxByOrNull { it.name }
        ?.name ?: "34.0.0"

    val d8Path = if (System.getProperty("os.name").lowercase().contains("win")) {
        "$androidHome/build-tools/$latestBuildTools/d8.bat"
    } else {
        "$androidHome/build-tools/$latestBuildTools/d8"
    }

    doFirst {
        println("🔧 Using d8 from: $d8Path")
        println("📂 Input JAR: ${jarFile.get()}")
    }

    commandLine(
        d8Path,
        jarFile.get().asFile.absolutePath,
        "--output", outputDir.get().asFile.absolutePath
    )

    doLast {
        val dexFile = file("${outputDir.get()}/classes.dex")
        if (dexFile.exists()) {
            // 重新打包为包含 DEX 的 JAR
            val dexJar = file("${outputDir.get()}/lxb-core-dex.jar")
            ant.withGroovyBuilder {
                "zip"("destfile" to dexJar) {
                    "fileset"("dir" to outputDir.get().asFile) {
                        "include"("name" to "classes.dex")
                    }
                }
            }
            println("✅ DEX JAR built: $dexJar")
            println("📦 Size: ${dexJar.length()} bytes")
        }
    }
}

// 完整构建任务
tasks.register("buildDex") {
    dependsOn("dex")
    doLast {
        println("🎉 Build complete! Use: adb push lxb-core/build/libs/lxb-core-dex.jar /data/local/tmp/")
    }
}


dependencies {
    testImplementation("junit:junit:4.13.2")
}
