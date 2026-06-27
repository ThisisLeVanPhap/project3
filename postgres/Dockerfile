FROM postgres:16

COPY ensure-password.sh /usr/local/bin/ensure-password.sh
RUN chmod +x /usr/local/bin/ensure-password.sh

ENTRYPOINT ["ensure-password.sh"]
CMD ["postgres"]
