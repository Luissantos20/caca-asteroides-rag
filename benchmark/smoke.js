import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 1,
  iterations: 10,
};

const perguntas = [
  "como me inscrever no programa?",
  "o que é o caça asteroides?",
  "como configurar o astrometrica?",
  "preciso ser estudante para participar?",
  "qual a idade mínima?",
];

export default function () {
  const pergunta = perguntas[Math.floor(Math.random() * perguntas.length)];

  const payload = JSON.stringify({
    message: pergunta,
  });

  const params = {
    headers: { "Content-Type": "application/json" },
    timeout: "60s",
  };

  const res = http.post("http://localhost:8010/chat", payload, params);

  check(res, {
    "status is 200": (r) => r.status === 200,
    "tem campo answer": (r) => r.json("answer") !== undefined,
  });

  sleep(1);
}