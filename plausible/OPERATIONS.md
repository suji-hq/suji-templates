# Plausible database maintenance

This is an operator runbook, not release notes. The template keeps Plausible
Community Edition 3.2.1 and PostgreSQL 16, and pins ClickHouse to 26.3.58.5 on
the maintained 26.3 LTS branch. Existing installs remain on manual upgrades.

## Compatibility boundary

Plausible's upstream 3.2.1 compose still specifies ClickHouse 24.12. The
26.3 choice is a Suji-tested compatibility update, not an upstream Plausible
support promise. Do not replace it with a floating `latest`, `lts`, or 26.8+
image: Plausible 3.2.1 contains Ecto CH 0.8.2, whose structure-dump output is
incompatible with a ClickHouse 26.8 HTTP-format change. That fix is absent from
the published Plausible image.

References:

- [ClickHouse supported security branches](https://github.com/ClickHouse/ClickHouse/security/policy)
- [ClickHouse upgrade and downgrade guidance](https://clickhouse.com/docs/guides/oss/update)
- [Plausible 3.2.1 upstream compose](https://github.com/plausible/community-edition/blob/v3.2.1/compose.yml)
- [Ecto CH format compatibility fix](https://github.com/plausible/ecto_ch/pull/312)

## Before an existing installation is upgraded

1. Schedule downtime and stop the Plausible service first so it cannot accept
   events. Then stop PostgreSQL and ClickHouse cleanly. This is a single-node
   database upgrade spanning more than one year of ClickHouse releases; do not
   promise a rolling or zero-downtime upgrade.
2. Inventory the actual container mounts and record the exact old image IDs,
   compose, and protected environment configuration. Back up all persistent
   data, including PostgreSQL, ClickHouse and any Plausible application volume.
   Container image metadata can contain secrets: keep the full inventory private.
3. Make cold volume snapshots or archives while **all three services remain
   stopped**. Preserve numeric ownership and modes. Store backup hashes and
   copies outside the VM, and verify a restore onto separate volumes before
   relying on them. A backup of ClickHouse alone is not an application backup.
4. Ensure enough free disk for the image, database rewrite/merge work, backup
   and restore, and enough memory for the configured service limits. The small
   synthetic validation below does not establish capacity for a large dataset.
5. Change only the ClickHouse image to the exact tag in `compose.yaml`. Start
   the databases, wait for them to accept connections, then start Plausible
   through the existing `createdb` / `migrate` / `run` command. Preserve the
   database password, `SECRET_KEY_BASE`, public URL and volume identities.
6. Check all service logs, OOM/restart state and migration results. Compare
   historical totals, dates and pages with the recorded baseline; submit a test
   event and verify it is added to the native dashboard. Verify owner access,
   anonymous access denial and the generated tracking script.

## Rollback

Do not run ClickHouse 24.12 against a volume that 26.3 has modified. An image
tag reversal alone is not the tested rollback path. Stop all three services,
restore the pre-upgrade backups to **new** empty volumes, select those volumes
in the protected compose configuration, restore the old images/configuration,
and verify the baseline again. Keep the failed-upgrade volumes untouched for
diagnosis until the restored application is accepted. Events accepted after
the backup are absent from the restored snapshot and require a separate
recovery decision.

Never use `docker compose down --volumes` on an existing installation as an
upgrade or rollback step. Remove only disposable test volumes or old volumes
whose backup and retention decision have been explicitly confirmed.

## Reproducing the release validation

Use a disposable native amd64 Docker project with a dedicated internal network,
no published ports, fresh named volumes and ephemeral generated secrets. Expose
the app only through an SSH tunnel bound to operator localhost. Use the same
512 MiB PostgreSQL / 1024 MiB ClickHouse / 1024 MiB app limits as the template.

1. Start the previous template with ClickHouse 24.12.6.70. Through the real
   Plausible UI create a dummy account and site, allow the native site cache to
   refresh, then submit one pageview to `/api/event` with a normal browser user
   agent. A 202 response alone is insufficient: check that the response does not
   carry `X-Plausible-Dropped: 1`. The native dashboard must show one pageview
   and its statistics endpoints must return 200.
2. Stop all services and archive every volume. Start the same volumes with
   ClickHouse 26.3.58.5 and unchanged Plausible/PostgreSQL. Verify the old
   pageview remains, submit another, and verify the total becomes two.
3. On both versions, verify the embedded adapter can dump the ingestion schema:

   ```sh
   docker compose exec -T plausible /app/bin/plausible rpc \
     'IO.inspect(Ecto.Adapters.ClickHouse.Structure.structure_dump("/tmp", Plausible.IngestRepo.config()))'
   ```

   The command must return `{:ok, "/tmp/structure.sql"}`. This is a schema
   compatibility probe; it is not a backup of the event data.

4. Stop everything, restore the cold archives to separate volumes, start the
   original 24.12 images and verify the original one-pageview baseline.
5. Finally test the new template on entirely empty volumes, including native
   database creation/migrations and the account/site/event/dashboard flow.
6. Remove only the test project's containers, networks, volumes, archives and
   credentials. Record the remaining-resource check.

This validates the exercised schema and synthetic workload. It does not test
customer data, very large datasets, every analytics feature, external email,
or a downgrade of the modified database files.
