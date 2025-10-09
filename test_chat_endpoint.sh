#!/bin/bash

# Test 1: New necessity
echo "=========================================="
echo "Test 1: New necessity"
echo "=========================================="
curl -X POST http://localhost:5002/api/etp-dynamic/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id":"aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "message":"uma empresa especializada em gestão de frota de aeronaves comerciais, precisa contratar um sistema de manutenção preditiva",
    "conversation_history":[],
    "need":"",
    "requirements":[],
    "version":0
}'

echo -e "\n\n"

# Test 2: Incremental edit
echo "=========================================="
echo "Test 2: Incremental edit"
echo "=========================================="
curl -X POST http://localhost:5002/api/etp-dynamic/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id":"aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "message":"inclua mais requisitos, e troque o R1",
    "conversation_history":[
      {"role":"user","content":"uma empresa especializada em gestão de frota de aeronaves comerciais, precisa contratar um sistema de manutenção preditiva"},
      {"role":"assistant","content":"Entendi! Você precisa de um sistema para gestão de frota de aeronaves."}
    ],
    "need":"sistema de manutenção preditiva para gestão de frota de aeronaves",
    "requirements":[
      {"id":"R1","text":"Sistema deve integrar com sensores IoT das aeronaves"},
      {"id":"R2","text":"Suporte a análise preditiva usando Machine Learning"},
      {"id":"R3","text":"Dashboard em tempo real para monitoramento"},
      {"id":"R4","text":"Alertas automáticos de manutenção necessária"}
    ],
    "version":1
}'

echo -e "\n\n"
