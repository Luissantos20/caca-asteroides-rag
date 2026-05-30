import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    warmup: {
      executor: "constant-vus",
      vus: 1,
      duration: "20s",
      gracefulStop: "5s",
      exec: "warmupRequest",
    },
    stress: {
      executor: "ramping-vus",
      startTime: "25s",
      startVUs: 1,
      stages: [
        { duration: "30s", target: 5 },
        { duration: "30s", target: 10 },
        { duration: "30s", target: 20 },
        { duration: "30s", target: 30 },
        { duration: "30s", target: 0 },
      ],
      gracefulRampDown: "10s",
      exec: "stressRequest",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<30000"],
    http_req_failed: ["rate<0.10"],
  },
};

const perguntas = [
  "como me inscrever no programa?",
  "o que é o caça asteroides?",
  "como configurar o astrometrica?",
  "preciso ser estudante para participar?",
  "qual a idade mínima?",
  "como funciona a detecção?",
  "qual o cronograma do programa?",
  "preciso de equipamento próprio?",
];

function fazerRequisicao() {
  const pergunta = perguntas[Math.floor(Math.random() * perguntas.length)];
  const payload = JSON.stringify({ message: pergunta });
  const params = {
    headers: { "Content-Type": "application/json" },
    timeout: "90s",
  };

  const res = http.post("http://localhost:8010/chat", payload, params);

  check(res, {
    "status is 200": (r) => r.status === 200,
    "tem campo answer": (r) => r.json("answer") !== undefined,
    "should_answer is true": (r) => r.json("should_answer") === true,
  });
}

export function warmupRequest() {
  fazerRequisicao();
  sleep(1);
}

export function stressRequest() {
  fazerRequisicao();
  sleep(2);
}