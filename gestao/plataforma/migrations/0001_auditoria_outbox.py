"""Trilha de auditoria garantida pelo banco + outbox transacional.

- `auditoria_evento`: append-only (UPDATE/DELETE/TRUNCATE bloqueados por
  trigger), com cadeia de hash SHA-256 serializada por advisory lock.
- `auditoria_registrar()`: trigger genérico; lê o contexto da sessão
  (`app.usuario_id`, `app.ip`, `app.requisicao_id`) definido pelo middleware.
"""

from django.db import migrations, models

SQL_AUDITORIA = r"""
CREATE TABLE auditoria_evento (
    id            bigserial PRIMARY KEY,
    ocorrido_em   timestamptz NOT NULL DEFAULT clock_timestamp(),
    tabela        text        NOT NULL,
    registro_id   text        NOT NULL,
    operacao      varchar(6)  NOT NULL CHECK (operacao IN ('INSERT', 'UPDATE', 'DELETE')),
    usuario_id    bigint,
    ip            inet,
    requisicao_id text,
    antes         jsonb,
    depois        jsonb,
    alterados     jsonb,
    hash_anterior text,
    hash          text        NOT NULL
);
CREATE INDEX auditoria_evento_registro_idx ON auditoria_evento (tabela, registro_id, id);
CREATE INDEX auditoria_evento_usuario_idx ON auditoria_evento (usuario_id, id);

-- Texto canônico usado no hash (mesma função usada na verificação).
CREATE FUNCTION auditoria_conteudo(e auditoria_evento) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT concat_ws('|', to_char(e.ocorrido_em AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US'), e.tabela, e.registro_id, e.operacao,
                     coalesce(e.usuario_id::text, ''), coalesce(e.ip::text, ''),
                     coalesce(e.requisicao_id, ''), coalesce(e.antes::text, ''),
                     coalesce(e.depois::text, ''))
$$;

CREATE FUNCTION auditoria_bloquear_alteracao() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'auditoria_evento é somente inserção (operação % negada)', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;

CREATE TRIGGER auditoria_evento_imutavel
    BEFORE UPDATE OR DELETE ON auditoria_evento
    FOR EACH ROW EXECUTE FUNCTION auditoria_bloquear_alteracao();
CREATE TRIGGER auditoria_evento_sem_truncate
    BEFORE TRUNCATE ON auditoria_evento
    FOR EACH STATEMENT EXECUTE FUNCTION auditoria_bloquear_alteracao();

-- Colunas que nunca entram no registro (segredos).
CREATE FUNCTION auditoria_sanitizar(dado jsonb) RETURNS jsonb
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN dado IS NULL THEN NULL
                ELSE dado - 'password' - 'senha' - 'token' END
$$;

CREATE FUNCTION auditoria_registrar() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_antes     jsonb;
    v_depois    jsonb;
    v_alterados jsonb;
    v_id        text;
    v_usuario   bigint;
    v_ip        inet;
    v_req       text;
    v_anterior  text;
    v_evento    auditoria_evento;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        v_antes := auditoria_sanitizar(to_jsonb(OLD));
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        v_depois := auditoria_sanitizar(to_jsonb(NEW));
    END IF;
    IF TG_OP = 'UPDATE' THEN
        SELECT coalesce(jsonb_agg(chave ORDER BY chave), '[]'::jsonb) INTO v_alterados
          FROM jsonb_object_keys(v_depois) AS chave
         WHERE v_depois -> chave IS DISTINCT FROM v_antes -> chave;
        IF v_alterados = '[]'::jsonb THEN
            RETURN NULL;  -- UPDATE sem mudança efetiva não polui a trilha
        END IF;
    END IF;
    v_id := coalesce(v_depois ->> 'id', v_antes ->> 'id');
    v_usuario := nullif(current_setting('app.usuario_id', true), '')::bigint;
    v_ip := nullif(current_setting('app.ip', true), '')::inet;
    v_req := nullif(current_setting('app.requisicao_id', true), '');

    -- Serializa a cadeia de hash (volume baixo; integridade > vazão).
    PERFORM pg_advisory_xact_lock(7438001);
    SELECT hash INTO v_anterior FROM auditoria_evento ORDER BY id DESC LIMIT 1;

    v_evento.ocorrido_em := clock_timestamp();
    v_evento.tabela := TG_TABLE_NAME;
    v_evento.registro_id := v_id;
    v_evento.operacao := TG_OP;
    v_evento.usuario_id := v_usuario;
    v_evento.ip := v_ip;
    v_evento.requisicao_id := v_req;
    v_evento.antes := v_antes;
    v_evento.depois := v_depois;

    INSERT INTO auditoria_evento (ocorrido_em, tabela, registro_id, operacao, usuario_id, ip,
                                  requisicao_id, antes, depois, alterados, hash_anterior, hash)
    VALUES (v_evento.ocorrido_em, TG_TABLE_NAME, v_id, TG_OP, v_usuario, v_ip, v_req,
            v_antes, v_depois, v_alterados, v_anterior,
            encode(sha256(convert_to(coalesce(v_anterior, '') || auditoria_conteudo(v_evento),
                                     'UTF8')), 'hex'));
    RETURN NULL;
END;
$$;
"""

SQL_AUDITORIA_REVERSO = r"""
DROP FUNCTION IF EXISTS auditoria_registrar() CASCADE;
DROP TABLE IF EXISTS auditoria_evento CASCADE;
DROP FUNCTION IF EXISTS auditoria_bloquear_alteracao() CASCADE;
DROP FUNCTION IF EXISTS auditoria_sanitizar(jsonb);
DROP FUNCTION IF EXISTS auditoria_conteudo(auditoria_evento);
"""


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.RunSQL(SQL_AUDITORIA, SQL_AUDITORIA_REVERSO),
        migrations.CreateModel(
            name="EventoAuditoria",
            fields=[("id", models.BigAutoField(primary_key=True, serialize=False))],
            options={"managed": False, "db_table": "auditoria_evento", "ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="MensagemOutbox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False,
                                           verbose_name="ID")),
                ("topico", models.CharField(max_length=100)),
                ("payload", models.JSONField(default=dict)),
                ("chave_idempotencia", models.CharField(max_length=200, unique=True)),
                ("situacao", models.CharField(
                    choices=[("pendente", "Pendente"), ("processada", "Processada"),
                             ("falhou", "Falhou definitivamente")],
                    default="pendente", max_length=12)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("disponivel_em", models.DateTimeField()),
                ("tentativas", models.PositiveSmallIntegerField(default=0)),
                ("processada_em", models.DateTimeField(blank=True, null=True)),
                ("ultimo_erro", models.TextField(blank=True)),
            ],
            options={
                "db_table": "plataforma_outbox",
                "indexes": [models.Index(condition=models.Q(("situacao", "pendente")),
                                         fields=["disponivel_em"], name="outbox_pendentes_idx")],
            },
        ),
    ]
