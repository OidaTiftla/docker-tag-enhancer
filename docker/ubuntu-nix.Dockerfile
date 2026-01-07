# syntax=docker/dockerfile:1.20
FROM ubuntu:24.04

LABEL org.opencontainers.image.description="Ubuntu base image with Nix package manager preinstalled"

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      gnupg \
      locales \
      xz-utils \
      sudo \
    && rm -rf /var/lib/apt/lists/* \
    && locale-gen en_US.UTF-8

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

ARG USERNAME=ubuntu
ARG USER_UID=1000
ARG USER_GID=1000

RUN echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/${USERNAME} \
    && mkdir -p /nix \
    && chown ${USERNAME}:${USERNAME} /nix

ENV USER=${USERNAME} \
    HOME=/home/${USERNAME}

USER ${USERNAME}
SHELL ["/bin/bash", "-c"]

# Install Nix in single-user (--no-daemon) mode and enable flakes/related tooling by default.
RUN curl -L https://nixos.org/nix/install -o /tmp/install-nix.sh \
    && sudo -u ${USERNAME} sh /tmp/install-nix.sh --daemon \
    && rm /tmp/install-nix.sh

WORKDIR /workspace
CMD ["/bin/bash"]
