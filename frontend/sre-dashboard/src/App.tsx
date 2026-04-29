import { useEffect, useState, useRef } from "react";
import {
  Box,
  Container,
  TextField,
  IconButton,
  Typography,
  Paper,
  Stack,
  Divider,
  CircularProgress,
} from "@mui/material";
import SendIcon from "@mui/icons-material/Send";
import { sendChat } from "./api";
import type { ChatMessage } from "./types";

function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  // ✅ SEND (UNCHANGED)
  const send = async () => {
    if (!input.trim()) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    const res = await sendChat(userMsg.content);
    if (!res?.incident_id) return;

    setMessages((prev) => [
      ...prev,
      {
        id: res.incident_id,
        role: "assistant",
        content: res.summary,
        incident: res,
        timestamp: new Date().toISOString(),
      },
    ]);
  };

  // ✅ POLLING (UNCHANGED)
  useEffect(() => {
    const pending = messages.find(
      (m) =>
        m.incident?.incident_id &&
        !m.incident.raw_output?.sections?.some(
          (s: any) => s.type === "rca"
        )
    );
    if (!pending) return;

    const id = pending.incident!.incident_id;
    if (!id) return;

    const interval = setInterval(async () => {
      const res = await fetch(`http://localhost:8000/incident/${id}`);
      if (!res.ok) return;

      const updated = await res.json();
      if (!updated?.raw_output?.sections) return;

      const hasRCA = updated.raw_output.sections.some(
        (s: any) => s.type === "rca"
      );

      if (hasRCA) {
        setMessages((prev) =>
          prev.map((m) =>
            m.incident?.incident_id === id
              ? { ...m, incident: updated }
              : m
          )
        );
        clearInterval(interval);
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [messages]);

  // ✅ AUTO‑SCROLL
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ✅ RENDER RCA CONTENT (UNCHANGED)
  const renderRCAContent = (content: string) => {
    const blocks = content.split("```");

    return blocks.map((block, blockIdx) => {
      if (blockIdx % 2 === 1) {
        const lines = block.trim().split("\n");

        // Detect optional language tag (e.g. "bash", "yaml")
        const firstLine = lines[0].trim();
        const isLanguage =
          /^[a-zA-Z]+$/.test(firstLine) && lines.length > 1;

        const language = isLanguage ? firstLine : null;
        const code = isLanguage ? lines.slice(1).join("\n") : block.trim();

        return (
          <Box
            key={blockIdx}
            sx={{
              bgcolor: "#0f172a",
              color: "#e5e7eb",
              borderRadius: 1,
              my: 2,
              overflowX: "auto",
            }}
          >
            {language && (
              <Box
                sx={{
                  px: 1.5,
                  py: 0.5,
                  fontSize: "0.7rem",
                  color: "#93c5fd",
                  borderBottom: "1px solid #1e293b",
                  fontFamily: "monospace",
                }}
              >
                {language}
              </Box>
            )}

            <Box
              component="pre"
              sx={{
                m: 0,
                p: 2,
                fontFamily: "monospace",
                fontSize: "0.85rem",
                whiteSpace: "pre",
              }}
            >
              {code}
            </Box>
          </Box>
        );
      }

      return block.split("\n").map((line, idx) => {
        const t = line.trim();
        if (!t) return null;

        if (t.startsWith("###")) {
          return (
            <Box key={`${blockIdx}-h-${idx}`} mt={3}>
              <Typography variant="h6" fontWeight={700}>
                {t.replace("###", "").trim()}
              </Typography>
              <Divider sx={{ mt: 1 }} />
            </Box>
          );
        }

        const stepMatch = t.match(/^(\d+)\.\s+\*\*(.+?)\*\*:?/);
        if (stepMatch) {
          return (
            <Typography
              key={`${blockIdx}-step-${idx}`}
              sx={{ fontWeight: 700, mt: 2 }}
            >
              {stepMatch[1]}. {stepMatch[2]}
            </Typography>
          );
        }

        return (
          <Typography
            key={`${blockIdx}-p-${idx}`}
            sx={{ mt: 1, lineHeight: 1.7 }}
          >
            {t.replace(/\*\*/g, "")}
          </Typography>
        );
      });
    });
  };

  return (
    <Box
      sx={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        bgcolor: "#f8fafc",
      }}
    >
      {/* HEADER */}
      <Box sx={{ p: 2, borderBottom: "1px solid #e5e7eb", bgcolor: "white" }}>
        <Typography variant="h6" fontWeight={600}>
          K8s DevOps Copilot
        </Typography>
      </Box>

      {/* CHAT */}
      <Box sx={{ flex: 1, overflowY: "auto" }}>
        <Container maxWidth="md" sx={{ py: 3 }}>
          <Stack spacing={3}>
            {messages.map((m) => {
              const sections = m.incident?.raw_output?.sections || [];
              const hasRCA = sections.some((s: any) => s.type === "rca");

              return (
                <Box
                  key={m.id}
                  sx={{
                    display: "flex",
                    justifyContent:
                      m.role === "user" ? "flex-end" : "flex-start",
                  }}
                >
                  <Paper
                    elevation={0}
                    sx={{
                      p: 3,
                      maxWidth: "75%",
                      borderRadius: 2,
                      bgcolor:
                        m.role === "user" ? "#e3f2fd" : "white",
                      border:
                        m.role === "assistant"
                          ? "1px solid #e5e7eb"
                          : "none",
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{ fontWeight: 600, color: "#64748b" }}
                    >
                      {m.role === "user" ? "You" : "DevOps AI"}
                    </Typography>

                    <Typography sx={{ mt: 1 }}>
                      {m.content}
                    </Typography>

                    {sections.map((section: any, idx: number) => (
                      <Box key={`${section.type}-${idx}`} mt={3}>
                        {section.type === "problems" && (
                          <>
                            <Divider sx={{ my: 2 }} />
                            <Typography fontWeight={700}>
                              ⚠️ Problematic Pods
                            </Typography>
                            <Divider sx={{ my: 1 }} />
                            {section.items.map((item: string) => (
                              <Typography
                                key={item}
                                sx={{ fontFamily: "monospace" }}
                              >
                                {item}
                              </Typography>
                            ))}
                          </>
                        )}

                        {section.type === "pods" && (
                          <>
                            <Divider sx={{ my: 3 }} />
                            <Typography fontWeight={700}>
                              📦 Pod Status
                            </Typography>
                            <Divider sx={{ my: 1 }} />
                            {section.items.map((p: any) => (
                              <Typography
                                key={`${p.namespace}-${p.pod}`}
                                sx={{ fontFamily: "monospace" }}
                              >
                                {p.namespace}/{p.pod} — {p.status}
                              </Typography>
                            ))}
                          </>
                        )}

                        {section.type === "rca" && (
                          <>
                            <Divider sx={{ my: 3 }} />
                            <Typography fontWeight={800}>
                              ✅ Root Cause Analysis
                            </Typography>
                            <Divider sx={{ my: 1 }} />
                            {renderRCAContent(section.content)}
                          </>
                        )}
                      </Box>
                    ))}

                    {/* ✅ RCA LOADING INDICATOR (FIXED CONDITION) */}
                    {m.role === "assistant" &&
                      m.incident?.analysis_status === "PENDING" && (
                        <Box
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 1,
                            mt: 3,
                            color: "#d97706",
                          }}
                        >
                          <CircularProgress size={16} />
                          <Typography sx={{ fontStyle: "italic" }}>
                            DevOps AI is analyzing root cause…
                          </Typography>
                        </Box>
                      )}
                  </Paper>
                </Box>
              );
            })}
            <div ref={bottomRef} />
          </Stack>
        </Container>
      </Box>

      {/* INPUT */}
      <Box
        sx={{
          p: 2,
          borderTop: "1px solid #e5e7eb",
          bgcolor: "white",
          position: "sticky",
          bottom: 0,
        }}
      >
        <Container maxWidth="md" sx={{ display: "flex", gap: 1 }}>
          <TextField
            fullWidth
            placeholder="Ask DevOps AI…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <IconButton
            color="primary"
            onClick={send}
            disabled={!input.trim()}
          >
            <SendIcon />
          </IconButton>
        </Container>
      </Box>
    </Box>
  );
}

export default App;