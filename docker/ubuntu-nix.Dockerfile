# syntax=docker/dockerfile:1.19
FROM python:3.14.2-slim

LABEL org.opencontainers.image.description="Python base image with Nix package manager preinstalled"

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
      skopeo \
      jq \
    && rm -rf /var/lib/apt/lists/* \
    && locale-gen en_US.UTF-8

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

ARG USERNAME=ubuntu
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m ${USERNAME}
RUN echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/${USERNAME} \
    && mkdir -p /nix \
    && chown ${USERNAME}:${USERNAME} /nix

ENV USER=${USERNAME} \
    HOME=/home/${USERNAME}

USER ${USERNAME}
SHELL ["/bin/bash", "-c"]

# Install Nix in single-user (--no-daemon) mode and enable flakes/related tooling by default.
RUN curl -L https://nixos.org/nix/install -o /tmp/install-nix.sh \
    && sudo -u ${USERNAME} sh /tmp/install-nix.sh --no-daemon \
    && rm /tmp/install-nix.sh \
    && echo ". ${HOME}/.nix-profile/etc/profile.d/nix.sh" >> ${HOME}/.bashrc

WORKDIR /workspace
CMD ["/bin/bash"]
