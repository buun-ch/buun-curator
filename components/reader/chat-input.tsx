"use client";

import * as React from "react";
import { useMemo, useRef, useState, useCallback } from "react";
import TextareaAutosize from "react-textarea-autosize";
import { useCopilotContext } from "@copilotkit/react-core";
import { useChatContext } from "@copilotkit/react-ui";
import { MessageSquare, Search, Send, Square } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";
import type { InputProps } from "@copilotkit/react-ui";

/** Chat mode for the assistant. */
export type ChatMode = "dialogue" | "research";

interface ChatInputProps extends InputProps {
  /** Current chat mode. */
  mode: ChatMode;
  /** Callback when mode changes. */
  onModeChange: (mode: ChatMode) => void;
}

const MIN_ROWS = 1;
const MAX_ROWS = 6;

/**
 * Custom chat input with mode toggle buttons (dialogue/research).
 *
 * Based on CopilotKit's default Input component with added mode buttons
 * in the bottom-left corner.
 */
export function ChatInput({
  inProgress,
  onSend,
  chatReady = false,
  onStop,
  hideStopButton = false,
  mode,
  onModeChange,
}: ChatInputProps) {
  const context = useChatContext();
  const copilotContext = useCopilotContext();
  const showPoweredBy = !copilotContext.copilotApiConfig?.publicApiKey;

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isComposing, setIsComposing] = useState(false);
  const [text, setText] = useState("");

  const handleDivClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      const target = event.target as HTMLElement;
      if (target.closest("button")) return;
      if (target.tagName === "TEXTAREA") return;
      textareaRef.current?.focus();
    },
    [],
  );

  const send = useCallback(() => {
    if (inProgress) return;
    onSend(text);
    setText("");
    textareaRef.current?.focus();
  }, [inProgress, onSend, text]);

  const isInProgress = inProgress;

  const { buttonIcon, buttonAlt } = useMemo(() => {
    if (!chatReady)
      return {
        buttonIcon: context.icons.spinnerIcon,
        buttonAlt: "Loading",
      };
    return isInProgress && !hideStopButton && chatReady
      ? {
          buttonIcon: <Square className="size-4" />,
          buttonAlt: "Stop",
        }
      : {
          buttonIcon: <Send className="size-4" />,
          buttonAlt: "Send",
        };
  }, [
    isInProgress,
    chatReady,
    hideStopButton,
    context.icons.spinnerIcon,
  ]);

  const canSend = useMemo(() => {
    return !isInProgress && text.trim().length > 0;
  }, [isInProgress, text]);

  const canStop = useMemo(() => {
    return isInProgress && !hideStopButton;
  }, [isInProgress, hideStopButton]);

  const sendDisabled = !canSend && !canStop;

  return (
    <div
      className={cn(
        "copilotKitInputContainer mb-3",
        showPoweredBy && "poweredByContainer",
      )}
    >
      <div className="copilotKitInput" onClick={handleDivClick}>
        <TextareaAutosize
          ref={textareaRef}
          placeholder={context.labels.placeholder}
          autoFocus={false}
          minRows={MIN_ROWS}
          maxRows={MAX_ROWS}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={() => setIsComposing(false)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !isComposing) {
              event.preventDefault();
              if (canSend) {
                send();
              }
            }
          }}
          style={{ resize: "none" }}
        />
        <div className="copilotKitInputControls">
          {/* Mode toggle buttons on the left */}
          <div className="flex items-center gap-0.5 rounded-md border bg-muted/50 p-0.5">
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => onModeChange("dialogue")}
                  className={cn(
                    "flex items-center justify-center rounded px-2 py-1 transition-colors",
                    mode === "dialogue"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                  aria-label="Dialogue mode"
                  aria-pressed={mode === "dialogue"}
                >
                  <MessageSquare className="size-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top">Dialogue</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => onModeChange("research")}
                  className={cn(
                    "flex items-center justify-center rounded px-2 py-1 transition-colors",
                    mode === "research"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                  aria-label="Research mode"
                  aria-pressed={mode === "research"}
                >
                  <Search className="size-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top">Research</TooltipContent>
            </Tooltip>
          </div>

          {/* Spacer */}
          <div style={{ flexGrow: 1 }} />

          {/* Send/Stop button on the right */}
          <button
            disabled={sendDisabled}
            onClick={isInProgress && !hideStopButton ? onStop : send}
            data-copilotkit-in-progress={inProgress}
            data-test-id={
              inProgress ? "copilot-chat-request-in-progress" : "copilot-chat-ready"
            }
            className="copilotKitInputControlButton"
            aria-label={buttonAlt}
          >
            {buttonIcon}
          </button>
        </div>
      </div>
    </div>
  );
}
