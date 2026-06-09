#!/usr/bin/env bash
# Generate gRPC Python stubs from proto files
# Run from the project root: bash scripts/generate_grpc.sh

set -e

PROTO_DIR="./proto"
SERVICES=("auth-service" "ai-service" "document-service" "analytics-service")

for SERVICE in "${SERVICES[@]}"; do
  OUT_DIR="./services/$SERVICE/src/grpc_generated"
  mkdir -p "$OUT_DIR"
  
  python -m grpc_tools.protoc \
    -I "$PROTO_DIR" \
    --python_out="$OUT_DIR" \
    --grpc_python_out="$OUT_DIR" \
    "$PROTO_DIR"/*.proto
  
  touch "$OUT_DIR/__init__.py"
  echo "Generated stubs for $SERVICE"
done

echo "All gRPC stubs generated successfully."
