"use client";

import { useCopilotChat } from "@copilotkit/react-core";
import {
  AssistantMessage as DefaultAssistantMessage,
  type AssistantMessageProps,
  CopilotChat,
} from "@copilotkit/react-ui";
import { AlertCircle, Bot, Plus, X } from "lucide-react";
import * as React from "react";
import { useCallback } from "react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import { ChatInput, type ChatMode } from "./chat-input";
import { ResearchStepsDisplay, useResearchSteps } from "./research-progress";

export type { ChatMode };

/** Custom AssistantMessage that shows research progress before the answer. */
function CustomAssistantMessage(props: AssistantMessageProps) {
  const steps = useResearchSteps();
  const { isCurrentMessage } = props;

  return (
    <>
      {/* Show progress only for the current (latest) message */}
      {isCurrentMessage && <ResearchStepsDisplay steps={steps} />}
      <DefaultAssistantMessage {...props} />
    </>
  );
}

/** Error message component for displaying chat errors inline. */
function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="mx-4 my-2 flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
      <AlertCircle className="mt-0.5 size-4 shrink-0" />
      <div className="flex-1">
        <p className="font-medium">Error</p>
        <p className="mt-1 text-xs opacity-90">{message}</p>
      </div>
    </div>
  );
}

interface AssistantSidebarProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** Current chat mode. */
  mode: ChatMode;
  /** Callback when mode changes. */
  onModeChange: (mode: ChatMode) => void;
  /** Callback when a new session is started (regenerates session ID). */
  onNewSession?: () => void;
}

export function AssistantSidebar({
  open = true,
  onOpenChange,
  mode,
  onModeChange,
  onNewSession,
}: AssistantSidebarProps) {
  // Get reset function from CopilotChat (must be called before any early return)
  const { reset } = useCopilotChat();

  const handleModeChange = useCallback(
    (newMode: ChatMode) => {
      onModeChange(newMode);
    },
    [onModeChange],
  );

  const handleNewChat = useCallback(() => {
    reset();
    onNewSession?.();
  }, [reset, onNewSession]);

  // Floating button when closed
  if (!open) {
    return (
      <Button
        variant="default"
        size="icon"
        className="fixed right-6 bottom-6 z-[99999] size-10 rounded-full shadow-lg"
        onClick={() => onOpenChange?.(true)}
      >
        <Bot className="size-5" />
      </Button>
    );
  }

  // Full sidebar when open
  return (
    <div className="flex h-full flex-col border-l bg-background">
      {/* Header */}
      <div className="flex h-12 shrink-0 items-center border-b px-3">
        <Bot className="mr-2 size-5" />
        <h2 className="flex-1 text-sm font-semibold select-none">
          AI Assistant
        </h2>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              onClick={handleNewChat}
            >
              <Plus className="size-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>New chat</TooltipContent>
        </Tooltip>
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={() => onOpenChange?.(false)}
        >
          <X className="size-4" />
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        <CopilotChat
          labels={{
            initial: "How can I help you understand this entry?",
          }}
          className="h-full"
          AssistantMessage={CustomAssistantMessage}
          Input={(props) => (
            <ChatInput {...props} mode={mode} onModeChange={handleModeChange} />
          )}
          ErrorMessage={({ error }) => (
            <ErrorMessage
              message={
                error instanceof Error
                  ? error.message
                  : "An unexpected error occurred"
              }
            />
          )}
        />
      </div>
    </div>
  );
}
