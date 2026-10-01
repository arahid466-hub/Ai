FROM python:3.12-slim-bookworm
ARG ANDROID_CMDLINE_TOOLS=11076708
ARG ANDROID_BUILD_TOOLS=35.0.0
ARG ANDROID_PLATFORM=android-35
ARG GRADLE_VERSION=8.7
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    AETHER_DATA_DIR=/data HF_HOME=/data/huggingface HUGGINGFACE_HUB_CACHE=/data/huggingface/hub \
    ANDROID_SDK_ROOT=/opt/android-sdk ANDROID_HOME=/opt/android-sdk \
    GRADLE_HOME=/opt/gradle PATH=/opt/gradle/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/build-tools/${ANDROID_BUILD_TOOLS}:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget git cmake build-essential gcc g++ clang \
    ffmpeg imagemagick espeak-ng openjdk-17-jre-headless nodejs npm unzip zip \
    && rm -rf /var/lib/apt/lists/*
# Install reproducible Gradle and Android command-line tooling at image build time.
RUN mkdir -p "$ANDROID_SDK_ROOT/cmdline-tools" /opt/gradle \
    && curl -fsSL --retry 5 "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_CMDLINE_TOOLS}_latest.zip" -o /tmp/cmdline.zip \
    && unzip -q /tmp/cmdline.zip -d "$ANDROID_SDK_ROOT/cmdline-tools" \
    && mv "$ANDROID_SDK_ROOT/cmdline-tools/cmdline-tools" "$ANDROID_SDK_ROOT/cmdline-tools/latest" \
    && rm /tmp/cmdline.zip \
    && yes | sdkmanager --licenses >/dev/null || true \
    && sdkmanager "platform-tools" "platforms;${ANDROID_PLATFORM}" "build-tools;${ANDROID_BUILD_TOOLS}" \
    && curl -fsSL --retry 5 "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" -o /tmp/gradle.zip \
    && unzip -q /tmp/gradle.zip -d /opt \
    && ln -s "/opt/gradle-${GRADLE_VERSION}"/bin /opt/gradle/bin \
    && rm /tmp/gradle.zip
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN git clone --depth 1 https://github.com/ggml-org/llama.cpp.git /opt/llama.cpp \
    && cmake -S /opt/llama.cpp -B /opt/llama.cpp/build -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=OFF -DGGML_CURL=OFF \
    && cmake --build /opt/llama.cpp/build --config Release -j2 --target llama-server
COPY . .
RUN chmod +x scripts/*.sh scripts/stable_diffusion_worker.py android/build-apk.sh \
    && mkdir -p /data/models /data/huggingface/hub /data/workspace /data/uploads /data/media /data/logs /data/jobs /data/cache \
    && python -m compileall -q . \
    && python --version && java -version && node --version && npm --version \
    && ffmpeg -version | head -n 1 && ffprobe -version | head -n 1 \
    && gradle --version | head -n 2 && sdkmanager --version && aapt2 version && apksigner --version && zipalign -h >/dev/null
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 CMD curl -fsS "http://127.0.0.1:${PORT:-8080}/health" || exit 1
CMD ["bash", "scripts/railway-entrypoint.sh"]
