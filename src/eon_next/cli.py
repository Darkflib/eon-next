"""Command-line interface for EON Next utility."""

import json
import sys

import click

from eon_next.client import EONNextClient


@click.command()
@click.option(
    "--username",
    "-u",
    required=True,
    envvar="EON_USERNAME",
    help="EON Next username (email). Can also be set via EON_USERNAME environment variable.",
)
@click.option(
    "--password",
    "-p",
    required=True,
    envvar="EON_PASSWORD",
    hide_input=True,
    help="EON Next password. Can also be set via EON_PASSWORD environment variable.",
)
@click.option(
    "--tariff",
    "-t",
    is_flag=True,
    help="Also retrieve tariff pricing information.",
)
@click.option(
    "--usage",
    is_flag=True,
    help="Also retrieve usage information.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output in JSON format.",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Do not use cached authentication token for this run.",
)
@click.option(
    "--clear-cache",
    is_flag=True,
    help="Clear cached authentication token before logging in.",
)
def main(
    username: str,
    password: str,
    tariff: bool,
    usage: bool,
    json_output: bool,
    no_cache: bool,
    clear_cache: bool,
) -> None:
    """EON Next CLI - Retrieve electricity credit balance and account information.

    This utility logs into your EON Next account and retrieves your current
    electricity credit balance. Optionally, it can also fetch tariff pricing
    and usage information.

    Examples:
        eon-next -u user@example.com -p password
        eon-next -u user@example.com -p password --tariff --usage
        eon-next -u user@example.com -p password --json
    """
    try:
        with EONNextClient(username, password, use_cache=not no_cache) as client:
            if clear_cache:
                click.echo("Clearing cached login token...", err=True)
                client.clear_cached_auth()

            # Log in
            click.echo("Logging in to EON Next...", err=True)
            client.login()
            click.echo("Successfully logged in.", err=True)

            # Get balance
            click.echo("Retrieving balance...", err=True)
            balance_info = client.get_balance()

            # Prepare output data
            output_data = {"balance": balance_info}

            # Get tariff if requested
            if tariff:
                click.echo("Retrieving tariff information...", err=True)
                tariff_info = client.get_tariff()
                output_data["tariff"] = tariff_info

            # Get usage if requested
            if usage:
                click.echo("Retrieving usage information...", err=True)
                usage_info = client.get_usage()
                output_data["usage"] = usage_info

            # Output results
            if json_output:
                click.echo(json.dumps(output_data, indent=2))
            else:
                click.echo("\n=== EON Next Account Information ===\n")
                click.echo(f"Balance: {balance_info.get('balance', 'N/A')}")

                if tariff:
                    click.echo("\n--- Tariff Information ---")
                    tariff_info = output_data["tariff"]
                    click.echo(f"Tariff Name: {tariff_info.get('tariff_name', 'N/A')}")
                    click.echo(f"Unit Rate: {tariff_info.get('unit_rate', 'N/A')}")
                    click.echo(f"Standing Charge: {tariff_info.get('standing_charge', 'N/A')}")

                if usage:
                    click.echo("\n--- Usage Information ---")
                    usage_info = output_data["usage"]
                    click.echo(f"Daily Usage: {usage_info.get('daily_usage', 'N/A')}")
                    click.echo(f"Weekly Usage: {usage_info.get('weekly_usage', 'N/A')}")
                    click.echo(f"Monthly Usage: {usage_info.get('monthly_usage', 'N/A')}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
