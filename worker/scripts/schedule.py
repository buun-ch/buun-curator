#!/usr/bin/env python
"""
CLI tool to manage Temporal schedules for Buun Curator.

Usage:
    # Show current ingest schedule
    uv run schedule show

    # Set ingest schedule (every 6 hours)
    uv run schedule set --interval 6h

    # Set ingest schedule with cron expression (default timezone: UTC)
    uv run schedule set --cron "0 */6 * * *"

    # Set ingest schedule with cron and explicit timezone (JST)
    uv run schedule set --cron "0,30 8-23 * * *" --timezone "Asia/Tokyo"

    # Note: Workflow config (auto_distill, enable_content_fetch, etc.) is read
    # from environment variables at runtime, not set in the schedule.

    # Pause schedule
    uv run schedule pause

    # Resume schedule
    uv run schedule resume

    # Delete schedule
    uv run schedule delete

    # Graph update schedule (separate from ingest)
    uv run schedule graph show
    uv run schedule graph set --interval 1h
    uv run schedule graph pause
    uv run schedule graph resume
    uv run schedule graph delete
    uv run schedule graph trigger

    # Entries cleanup schedule (delete old entries)
    uv run schedule cleanup show
    uv run schedule cleanup set --interval 1d
    uv run schedule cleanup set --interval 1d --days 14
    uv run schedule cleanup pause
    uv run schedule cleanup resume
    uv run schedule cleanup delete
    uv run schedule cleanup trigger
"""

import argparse
import asyncio
import logging
import re
from datetime import timedelta

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleIntervalSpec,
    ScheduleSpec,
    ScheduleUpdate,
    ScheduleUpdateInput,
)

from buun_curator.config import get_config
from buun_curator.models import (
    AllFeedsIngestionInput,
    EntriesCleanupInput,
    GlobalGraphUpdateInput,
)
from buun_curator.temporal import get_temporal_client
from buun_curator.workflows import (
    AllFeedsIngestionWorkflow,
    EntriesCleanupWorkflow,
    GlobalGraphUpdateWorkflow,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("schedule")

SCHEDULE_ID = "ingest-schedule"
WORKFLOW_ID = "ingest-scheduled"

GRAPH_SCHEDULE_ID = "graph-update-schedule"
GRAPH_WORKFLOW_ID = "graph-update-scheduled"

CLEANUP_SCHEDULE_ID = "entries-cleanup-schedule"
CLEANUP_WORKFLOW_ID = "entries-cleanup-scheduled"


def parse_interval(interval_str: str) -> timedelta:
    """
    Parse interval string to timedelta.

    Parameters
    ----------
    interval_str : str
        Interval string like "6h", "30m", "1d".

    Returns
    -------
    timedelta
        Parsed timedelta.

    Raises
    ------
    ValueError
        If interval string is invalid.
    """
    match = re.match(r"^(\d+)([smhd])$", interval_str.lower())
    if not match:
        raise ValueError(f"Invalid interval format: {interval_str}. Use format like 6h, 30m, 1d")

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "s":
        return timedelta(seconds=value)
    elif unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    else:
        raise ValueError(f"Unknown unit: {unit}")


async def show_schedule(client: Client) -> None:
    """
    Show current schedule status.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    try:
        handle = client.get_schedule_handle(SCHEDULE_ID)
        desc = await handle.describe()

        logger.info(f"Schedule ID: {SCHEDULE_ID}")
        logger.info(f"  State: {'paused' if desc.schedule.state.paused else 'active'}")

        # Show spec
        spec = desc.schedule.spec
        if spec.intervals:
            intervals = [str(i.every) for i in spec.intervals]
            logger.info(f"  Intervals: {', '.join(intervals)}")
        if spec.cron_expressions:
            logger.info(f"  Cron: {', '.join(spec.cron_expressions)}")
            logger.info(f"  Timezone: {spec.time_zone_name or 'UTC'}")

        # Show action
        action = desc.schedule.action
        if isinstance(action, ScheduleActionStartWorkflow):
            logger.info(f"  Workflow: {action.workflow}")
            logger.info(f"  Workflow ID: {action.id}")
            logger.info(f"  Task Queue: {action.task_queue}")
            if action.args:
                logger.info(f"  Args: {action.args}")

        # Show recent actions
        if desc.info.recent_actions:
            logger.info("  Recent runs:")
            for action_result in desc.info.recent_actions[-5:]:
                scheduled = action_result.scheduled_at
                started = action_result.started_at
                logger.info(f"    - Scheduled: {scheduled}, Started: {started}")

        # Show next run
        if desc.info.next_action_times:
            next_time = desc.info.next_action_times[0]
            logger.info(f"  Next run: {next_time}")

    except Exception as e:
        if "not found" in str(e).lower():
            logger.info(f"Schedule '{SCHEDULE_ID}' not found. Use 'schedule set' to create.")
        else:
            raise


async def set_schedule(
    client: Client,
    task_queue: str,
    interval: str | None = None,
    cron: str | None = None,
    timezone: str | None = None,
) -> None:
    """
    Create or update the ingest schedule.

    Workflow config (auto_distill, enable_content_fetch, max_concurrent,
    enable_thumbnail, domain_fetch_delay) is read from environment variables
    at runtime, not fixed at schedule creation time.

    Parameters
    ----------
    client : Client
        Temporal client.
    task_queue : str
        Task queue name.
    interval : str | None, optional
        Interval string like "6h" (default: None).
    cron : str | None, optional
        Cron expression (default: None).
    timezone : str | None, optional
        Timezone for cron expression, e.g., "Asia/Tokyo" (default: UTC).
    """
    if not interval and not cron:
        raise ValueError("Either --interval or --cron is required")

    # Build spec
    spec = ScheduleSpec()
    if interval:
        delta = parse_interval(interval)
        spec = ScheduleSpec(intervals=[ScheduleIntervalSpec(every=delta)])
        logger.info(f"Setting schedule with interval: {delta}")
    elif cron:
        spec = ScheduleSpec(
            cron_expressions=[cron],
            time_zone_name=timezone,
        )
        logger.info(f"Setting schedule with cron: {cron} (timezone: {timezone or 'UTC'})")

    # Build action with empty input - config is read from env vars at runtime
    action = ScheduleActionStartWorkflow(
        AllFeedsIngestionWorkflow.run,
        AllFeedsIngestionInput(),
        id=WORKFLOW_ID,
        task_queue=task_queue,
    )

    schedule = Schedule(action=action, spec=spec)

    # Try to create, or update if exists
    try:
        await client.create_schedule(
            SCHEDULE_ID,
            schedule,
        )
        logger.info(f"Created schedule '{SCHEDULE_ID}'")
    except ScheduleAlreadyRunningError:
        # Update existing schedule
        handle = client.get_schedule_handle(SCHEDULE_ID)

        async def updater(_input: ScheduleUpdateInput) -> ScheduleUpdate:
            return ScheduleUpdate(schedule=schedule)

        await handle.update(updater)
        logger.info(f"Updated schedule '{SCHEDULE_ID}'")

    logger.info("  Workflow config will be read from environment variables at runtime")


async def pause_schedule(client: Client) -> None:
    """
    Pause the ingest schedule.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    handle = client.get_schedule_handle(SCHEDULE_ID)
    await handle.pause(note="Paused via CLI")
    logger.info(f"Paused schedule '{SCHEDULE_ID}'")


async def resume_schedule(client: Client) -> None:
    """
    Resume the ingest schedule.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    handle = client.get_schedule_handle(SCHEDULE_ID)
    await handle.unpause(note="Resumed via CLI")
    logger.info(f"Resumed schedule '{SCHEDULE_ID}'")


async def delete_schedule(client: Client) -> None:
    """
    Delete the ingest schedule.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    handle = client.get_schedule_handle(SCHEDULE_ID)
    await handle.delete()
    logger.info(f"Deleted schedule '{SCHEDULE_ID}'")


async def trigger_schedule(client: Client) -> None:
    """
    Trigger the schedule immediately.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    handle = client.get_schedule_handle(SCHEDULE_ID)
    await handle.trigger()
    logger.info(f"Triggered schedule '{SCHEDULE_ID}'")


# ============================================================================
# Graph Update Schedule Functions
# ============================================================================


async def show_graph_schedule(client: Client) -> None:
    """
    Show current graph update schedule status.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    try:
        handle = client.get_schedule_handle(GRAPH_SCHEDULE_ID)
        desc = await handle.describe()

        logger.info(f"Schedule ID: {GRAPH_SCHEDULE_ID}")
        logger.info(f"  State: {'paused' if desc.schedule.state.paused else 'active'}")

        # Show spec
        spec = desc.schedule.spec
        if spec.intervals:
            intervals = [str(i.every) for i in spec.intervals]
            logger.info(f"  Intervals: {', '.join(intervals)}")
        if spec.cron_expressions:
            logger.info(f"  Cron: {', '.join(spec.cron_expressions)}")
            logger.info(f"  Timezone: {spec.time_zone_name or 'UTC'}")

        # Show action
        action = desc.schedule.action
        if isinstance(action, ScheduleActionStartWorkflow):
            logger.info(f"  Workflow: {action.workflow}")
            logger.info(f"  Workflow ID: {action.id}")
            logger.info(f"  Task Queue: {action.task_queue}")
            if action.args:
                logger.info(f"  Args: {action.args}")

        # Show recent actions
        if desc.info.recent_actions:
            logger.info("  Recent runs:")
            for action_result in desc.info.recent_actions[-5:]:
                scheduled = action_result.scheduled_at
                started = action_result.started_at
                logger.info(f"    - Scheduled: {scheduled}, Started: {started}")

        # Show next run
        if desc.info.next_action_times:
            next_time = desc.info.next_action_times[0]
            logger.info(f"  Next run: {next_time}")

    except Exception as e:
        if "not found" in str(e).lower():
            logger.info(
                f"Schedule '{GRAPH_SCHEDULE_ID}' not found. Use 'schedule graph set' to create."
            )
        else:
            raise


async def set_graph_schedule(
    client: Client,
    task_queue: str,
    interval: str | None = None,
    cron: str | None = None,
    timezone: str | None = None,
    batch_size: int = 50,
) -> None:
    """
    Create or update the graph update schedule.

    Parameters
    ----------
    client : Client
        Temporal client.
    task_queue : str
        Task queue name.
    interval : str | None, optional
        Interval string like "1h" (default: None).
    cron : str | None, optional
        Cron expression (default: None).
    timezone : str | None, optional
        Timezone for cron expression (default: UTC).
    batch_size : int, optional
        Entries per batch (default: 50).
    """
    if not interval and not cron:
        raise ValueError("Either --interval or --cron is required")

    # Build spec
    spec = ScheduleSpec()
    if interval:
        delta = parse_interval(interval)
        spec = ScheduleSpec(intervals=[ScheduleIntervalSpec(every=delta)])
        logger.info(f"Setting graph schedule with interval: {delta}")
    elif cron:
        spec = ScheduleSpec(
            cron_expressions=[cron],
            time_zone_name=timezone,
        )
        logger.info(f"Setting graph schedule with cron: {cron} (timezone: {timezone or 'UTC'})")

    # Build action
    action = ScheduleActionStartWorkflow(
        GlobalGraphUpdateWorkflow.run,
        GlobalGraphUpdateInput(batch_size=batch_size),
        id=GRAPH_WORKFLOW_ID,
        task_queue=task_queue,
    )

    schedule = Schedule(action=action, spec=spec)

    # Try to create, or update if exists
    try:
        await client.create_schedule(
            GRAPH_SCHEDULE_ID,
            schedule,
        )
        logger.info(f"Created schedule '{GRAPH_SCHEDULE_ID}'")
    except ScheduleAlreadyRunningError:
        # Update existing schedule
        handle = client.get_schedule_handle(GRAPH_SCHEDULE_ID)

        async def updater(_input: ScheduleUpdateInput) -> ScheduleUpdate:
            return ScheduleUpdate(schedule=schedule)

        await handle.update(updater)
        logger.info(f"Updated schedule '{GRAPH_SCHEDULE_ID}'")

    logger.info(f"  batch_size: {batch_size}")


async def pause_graph_schedule(client: Client) -> None:
    """
    Pause the graph update schedule.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    handle = client.get_schedule_handle(GRAPH_SCHEDULE_ID)
    await handle.pause(note="Paused via CLI")
    logger.info(f"Paused schedule '{GRAPH_SCHEDULE_ID}'")


async def resume_graph_schedule(client: Client) -> None:
    """
    Resume the graph update schedule.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    handle = client.get_schedule_handle(GRAPH_SCHEDULE_ID)
    await handle.unpause(note="Resumed via CLI")
    logger.info(f"Resumed schedule '{GRAPH_SCHEDULE_ID}'")


async def delete_graph_schedule(client: Client) -> None:
    """
    Delete the graph update schedule.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    handle = client.get_schedule_handle(GRAPH_SCHEDULE_ID)
    await handle.delete()
    logger.info(f"Deleted schedule '{GRAPH_SCHEDULE_ID}'")


async def trigger_graph_schedule(client: Client) -> None:
    """
    Trigger the graph update schedule immediately.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    handle = client.get_schedule_handle(GRAPH_SCHEDULE_ID)
    await handle.trigger()
    logger.info(f"Triggered schedule '{GRAPH_SCHEDULE_ID}'")


# ============================================================================
# Entries Cleanup Schedule Functions
# ============================================================================


async def show_cleanup_schedule(client: Client) -> None:
    """
    Show current entries cleanup schedule status.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    try:
        handle = client.get_schedule_handle(CLEANUP_SCHEDULE_ID)
        desc = await handle.describe()

        logger.info(f"Schedule ID: {CLEANUP_SCHEDULE_ID}")
        logger.info(f"  State: {'paused' if desc.schedule.state.paused else 'active'}")

        # Show spec
        spec = desc.schedule.spec
        if spec.intervals:
            intervals = [str(i.every) for i in spec.intervals]
            logger.info(f"  Intervals: {', '.join(intervals)}")
        if spec.cron_expressions:
            logger.info(f"  Cron: {', '.join(spec.cron_expressions)}")
            logger.info(f"  Timezone: {spec.time_zone_name or 'UTC'}")

        # Show action
        action = desc.schedule.action
        if isinstance(action, ScheduleActionStartWorkflow):
            logger.info(f"  Workflow: {action.workflow}")
            logger.info(f"  Workflow ID: {action.id}")
            logger.info(f"  Task Queue: {action.task_queue}")
            if action.args:
                logger.info(f"  Args: {action.args}")

        # Show recent actions
        if desc.info.recent_actions:
            logger.info("  Recent runs:")
            for action_result in desc.info.recent_actions[-5:]:
                scheduled = action_result.scheduled_at
                started = action_result.started_at
                logger.info(f"    - Scheduled: {scheduled}, Started: {started}")

        # Show next run
        if desc.info.next_action_times:
            next_time = desc.info.next_action_times[0]
            logger.info(f"  Next run: {next_time}")

    except Exception as e:
        if "not found" in str(e).lower():
            logger.info(
                f"Schedule '{CLEANUP_SCHEDULE_ID}' not found. Use 'schedule cleanup set' to create."
            )
        else:
            raise


async def set_cleanup_schedule(
    client: Client,
    task_queue: str,
    interval: str | None = None,
    cron: str | None = None,
    timezone: str | None = None,
    older_than_days: int = 7,
) -> None:
    """
    Create or update the entries cleanup schedule.

    Parameters
    ----------
    client : Client
        Temporal client.
    task_queue : str
        Task queue name.
    interval : str | None, optional
        Interval string like "1d" (default: None).
    cron : str | None, optional
        Cron expression (default: None).
    timezone : str | None, optional
        Timezone for cron expression (default: UTC).
    older_than_days : int, optional
        Delete entries older than this many days (default: 7).
    """
    if not interval and not cron:
        raise ValueError("Either --interval or --cron is required")

    # Build spec
    spec = ScheduleSpec()
    if interval:
        delta = parse_interval(interval)
        spec = ScheduleSpec(intervals=[ScheduleIntervalSpec(every=delta)])
        logger.info(f"Setting cleanup schedule with interval: {delta}")
    elif cron:
        spec = ScheduleSpec(
            cron_expressions=[cron],
            time_zone_name=timezone,
        )
        logger.info(f"Setting cleanup schedule with cron: {cron} (timezone: {timezone or 'UTC'})")

    # Build action
    action = ScheduleActionStartWorkflow(
        EntriesCleanupWorkflow.run,
        EntriesCleanupInput(older_than_days=older_than_days),
        id=CLEANUP_WORKFLOW_ID,
        task_queue=task_queue,
    )

    schedule = Schedule(action=action, spec=spec)

    # Try to create, or update if exists
    try:
        await client.create_schedule(
            CLEANUP_SCHEDULE_ID,
            schedule,
        )
        logger.info(f"Created schedule '{CLEANUP_SCHEDULE_ID}'")
    except ScheduleAlreadyRunningError:
        # Update existing schedule
        handle = client.get_schedule_handle(CLEANUP_SCHEDULE_ID)

        async def updater(_input: ScheduleUpdateInput) -> ScheduleUpdate:
            return ScheduleUpdate(schedule=schedule)

        await handle.update(updater)
        logger.info(f"Updated schedule '{CLEANUP_SCHEDULE_ID}'")

    logger.info(f"  older_than_days: {older_than_days}")


async def pause_cleanup_schedule(client: Client) -> None:
    """
    Pause the entries cleanup schedule.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    handle = client.get_schedule_handle(CLEANUP_SCHEDULE_ID)
    await handle.pause(note="Paused via CLI")
    logger.info(f"Paused schedule '{CLEANUP_SCHEDULE_ID}'")


async def resume_cleanup_schedule(client: Client) -> None:
    """
    Resume the entries cleanup schedule.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    handle = client.get_schedule_handle(CLEANUP_SCHEDULE_ID)
    await handle.unpause(note="Resumed via CLI")
    logger.info(f"Resumed schedule '{CLEANUP_SCHEDULE_ID}'")


async def delete_cleanup_schedule(client: Client) -> None:
    """
    Delete the entries cleanup schedule.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    handle = client.get_schedule_handle(CLEANUP_SCHEDULE_ID)
    await handle.delete()
    logger.info(f"Deleted schedule '{CLEANUP_SCHEDULE_ID}'")


async def trigger_cleanup_schedule(client: Client) -> None:
    """
    Trigger the entries cleanup schedule immediately.

    Parameters
    ----------
    client : Client
        Temporal client.
    """
    handle = client.get_schedule_handle(CLEANUP_SCHEDULE_ID)
    await handle.trigger()
    logger.info(f"Triggered schedule '{CLEANUP_SCHEDULE_ID}'")


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Manage Temporal schedules for Buun Curator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Show command
    subparsers.add_parser("show", help="Show current schedule status")

    # Set command
    set_parser = subparsers.add_parser("set", help="Create or update schedule")
    set_parser.add_argument(
        "--interval",
        help="Interval (e.g., 6h, 30m, 1d)",
    )
    set_parser.add_argument(
        "--cron",
        help="Cron expression (e.g., '0 */6 * * *')",
    )
    set_parser.add_argument(
        "--timezone",
        default="UTC",
        help="Timezone for cron expression (default: UTC)",
    )
    # Note: Workflow config (auto_distill, enable_content_fetch, enable_thumbnail,
    # max_concurrent, domain_fetch_delay) is read from environment variables at runtime

    # Pause command
    subparsers.add_parser("pause", help="Pause the schedule")

    # Resume command
    subparsers.add_parser("resume", help="Resume the schedule")

    # Delete command
    subparsers.add_parser("delete", help="Delete the schedule")

    # Trigger command
    subparsers.add_parser("trigger", help="Trigger the schedule immediately")

    # Graph subcommand with its own subcommands
    graph_parser = subparsers.add_parser("graph", help="Manage graph update schedule")
    graph_subparsers = graph_parser.add_subparsers(dest="graph_command", required=True)

    # Graph show command
    graph_subparsers.add_parser("show", help="Show current graph schedule status")

    # Graph set command
    graph_set_parser = graph_subparsers.add_parser("set", help="Create or update graph schedule")
    graph_set_parser.add_argument(
        "--interval",
        help="Interval (e.g., 1h, 30m)",
    )
    graph_set_parser.add_argument(
        "--cron",
        help="Cron expression (e.g., '0 * * * *')",
    )
    graph_set_parser.add_argument(
        "--timezone",
        default="UTC",
        help="Timezone for cron expression (default: UTC)",
    )
    graph_set_parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Entries per batch (default: from config or 50)",
    )

    # Graph pause command
    graph_subparsers.add_parser("pause", help="Pause the graph schedule")

    # Graph resume command
    graph_subparsers.add_parser("resume", help="Resume the graph schedule")

    # Graph delete command
    graph_subparsers.add_parser("delete", help="Delete the graph schedule")

    # Graph trigger command
    graph_subparsers.add_parser("trigger", help="Trigger the graph schedule immediately")

    # Cleanup subcommand with its own subcommands
    cleanup_parser = subparsers.add_parser("cleanup", help="Manage entries cleanup schedule")
    cleanup_subparsers = cleanup_parser.add_subparsers(dest="cleanup_command", required=True)

    # Cleanup show command
    cleanup_subparsers.add_parser("show", help="Show current cleanup schedule status")

    # Cleanup set command
    cleanup_set_parser = cleanup_subparsers.add_parser(
        "set", help="Create or update cleanup schedule"
    )
    cleanup_set_parser.add_argument(
        "--interval",
        help="Interval (e.g., 1d, 12h)",
    )
    cleanup_set_parser.add_argument(
        "--cron",
        help="Cron expression (e.g., '0 0 * * *')",
    )
    cleanup_set_parser.add_argument(
        "--timezone",
        default="UTC",
        help="Timezone for cron expression (default: UTC)",
    )
    cleanup_set_parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Delete entries older than this many days (default: 7)",
    )

    # Cleanup pause command
    cleanup_subparsers.add_parser("pause", help="Pause the cleanup schedule")

    # Cleanup resume command
    cleanup_subparsers.add_parser("resume", help="Resume the cleanup schedule")

    # Cleanup delete command
    cleanup_subparsers.add_parser("delete", help="Delete the cleanup schedule")

    # Cleanup trigger command
    cleanup_subparsers.add_parser("trigger", help="Trigger the cleanup schedule immediately")

    args = parser.parse_args()
    config = get_config()

    logger.info(
        f"Connecting to Temporal at {config.temporal_host} (namespace: {config.temporal_namespace})"
    )
    client = await get_temporal_client()

    if args.command == "show":
        await show_schedule(client)
    elif args.command == "set":
        if not args.interval and not args.cron:
            parser.error("Either --interval or --cron is required")
        await set_schedule(
            client,
            config.task_queue,
            interval=args.interval,
            cron=args.cron,
            timezone=args.timezone if args.cron else None,
        )
    elif args.command == "pause":
        await pause_schedule(client)
    elif args.command == "resume":
        await resume_schedule(client)
    elif args.command == "delete":
        await delete_schedule(client)
    elif args.command == "trigger":
        await trigger_schedule(client)
    elif args.command == "graph":
        if args.graph_command == "show":
            await show_graph_schedule(client)
        elif args.graph_command == "set":
            if not args.interval and not args.cron:
                graph_parser.error("Either --interval or --cron is required")
            await set_graph_schedule(
                client,
                config.task_queue,
                interval=args.interval,
                cron=args.cron,
                timezone=args.timezone if args.cron else None,
                batch_size=(
                    args.batch_size
                    if args.batch_size is not None
                    else config.global_graph_update_batch_size
                ),
            )
        elif args.graph_command == "pause":
            await pause_graph_schedule(client)
        elif args.graph_command == "resume":
            await resume_graph_schedule(client)
        elif args.graph_command == "delete":
            await delete_graph_schedule(client)
        elif args.graph_command == "trigger":
            await trigger_graph_schedule(client)
    elif args.command == "cleanup":
        if args.cleanup_command == "show":
            await show_cleanup_schedule(client)
        elif args.cleanup_command == "set":
            if not args.interval and not args.cron:
                cleanup_parser.error("Either --interval or --cron is required")
            await set_cleanup_schedule(
                client,
                config.task_queue,
                interval=args.interval,
                cron=args.cron,
                timezone=args.timezone if args.cron else None,
                older_than_days=args.days,
            )
        elif args.cleanup_command == "pause":
            await pause_cleanup_schedule(client)
        elif args.cleanup_command == "resume":
            await resume_cleanup_schedule(client)
        elif args.cleanup_command == "delete":
            await delete_cleanup_schedule(client)
        elif args.cleanup_command == "trigger":
            await trigger_cleanup_schedule(client)


def cli() -> None:
    """Entry point for the CLI."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()
