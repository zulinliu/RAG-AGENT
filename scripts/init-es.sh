#!/usr/bin/env bash
#
# Initialize Elasticsearch:
#   1. Wait for ES to be healthy
#   2. Install IK analysis plugin (if not present)
#   3. Create rag_chunks index with mapping
#
set -euo pipefail

ES_URL="${ELASTICSEARCH_URL:-http://elasticsearch:9200}"
INDEX_NAME="${ELASTICSEARCH_INDEX:-rag_chunks}"
MAPPINGS_FILE="/config/mappings.json"

echo "[init-es] Waiting for Elasticsearch at ${ES_URL} ..."

# Wait for Elasticsearch to be ready
MAX_RETRIES=60
RETRY=0
until curl -sf "${ES_URL}/_cluster/health?wait_for_status=yellow&timeout=5s" > /dev/null 2>&1; do
    RETRY=$((RETRY + 1))
    if [ "${RETRY}" -ge "${MAX_RETRIES}" ]; then
        echo "[init-es] ERROR: Elasticsearch not reachable after ${MAX_RETRIES} retries." >&2
        exit 1
    fi
    echo "[init-es] Retry ${RETRY}/${MAX_RETRIES} ..."
    sleep 3
done
echo "[init-es] Elasticsearch is ready."

# Check if IK plugin is installed, and install if missing
echo "[init-es] Checking IK analysis plugin ..."
PLUGINS=$(curl -sf "${ES_URL}/_cat/plugins?format=json" 2>/dev/null || echo "[]")

if echo "${PLUGINS}" | grep -q "analysis-ik" 2>/dev/null; then
    echo "[init-es] IK plugin already installed."
    HAS_IK=1
else
    HAS_IK=0
    echo "[init-es] IK plugin not found."
    echo "[init-es] To install the IK analyzer, run INSIDE the ES container:"
    echo "[init-es]   docker exec rag-elasticsearch bin/elasticsearch-plugin install https://get.infini.cloud/elasticsearch/analysis-ik/8.19.0"
    echo "[init-es]   docker restart rag-elasticsearch"
    echo "[init-es] Continuing with index creation (IK fields will use standard analyzer until plugin is installed)."
fi

# Create index if it does not exist
if curl -sf "${ES_URL}/${INDEX_NAME}" > /dev/null 2>&1; then
    echo "[init-es] Index '${INDEX_NAME}' already exists, skipping creation."
else
    echo "[init-es] Creating index '${INDEX_NAME}' ..."
    if [ -f "${MAPPINGS_FILE}" ] && [ "${HAS_IK}" = "1" ]; then
        curl -sf -X PUT "${ES_URL}/${INDEX_NAME}" \
            -H "Content-Type: application/json" \
            -d @"${MAPPINGS_FILE}"
        echo ""
        echo "[init-es] Index '${INDEX_NAME}' created with mapping from ${MAPPINGS_FILE}."
    else
        echo "[init-es] WARNING: IK mapping unavailable, creating index with standard analyzer fallback."
        curl -sf -X PUT "${ES_URL}/${INDEX_NAME}" \
            -H "Content-Type: application/json" \
            -d '{
              "settings": {"number_of_shards": 1, "number_of_replicas": 1},
              "mappings": {
                "properties": {
                  "project_id": {"type": "keyword"},
                  "document_id": {"type": "keyword"},
                  "chunk_id": {"type": "keyword"},
                  "content": {"type": "text"},
                  "title": {"type": "text"},
                  "parent_title": {"type": "text"},
                  "chunk_type": {"type": "keyword"},
                  "source_type": {"type": "keyword"},
                  "file_path": {"type": "keyword"},
                  "mime_type": {"type": "keyword"},
                  "created_at": {"type": "date", "format": "strict_date_optional_time||epoch_millis"},
                  "modified_at": {"type": "date", "format": "strict_date_optional_time||epoch_millis"}
                }
              }
            }'
        echo ""
        echo "[init-es] Index '${INDEX_NAME}' created with fallback mapping."
    fi
fi

# Verify index
echo "[init-es] Verifying index ..."
curl -sf "${ES_URL}/_cat/indices/${INDEX_NAME}?v"
echo ""

echo "[init-es] Done."
