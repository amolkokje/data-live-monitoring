#!/bin/bash

# This script deploys the infrastructure and starts all the importers

# default to host grafana and influx images locally. Can override BACKEND_HOST to remote server
BACKEND_HOST="localhost"

# --------------------------
# Utils
# --------------------------

log()
{
    echo "$(date +"%T.%3"): [$1] $2"
}

execute_command()
{
    CMD="$@"
    log "CMD" "$CMD"
    $CMD
}

# --------------------------
# Deploy
# --------------------------

function deploy_stack
{
    log "DEPLOY" "Deploying Stack ..."
    execute_command "cd ../infra"
    pwd
    docker-compose -f docker-compose.yml up &> log_server.log &
    log "DEPLOY" "Server logs at: ../infra/log_server.log"
    wait_for_stack_deploy
    log "DEPLOY" "Graphana Dashboards: http://$(hostname):3000"

    execute_command "cd ../scripts"
    pwd
    log "DEPLOY" "Start the data importing ..."
    execute_command "python start_data_import.py"
}

function wait_for_stack_deploy
{
    until curl -s http://localhost:8086/ping -o /dev/null; do
        echo Waiting for influxdb ...
        sleep 1
    done
    echo "Influxdb is up!"

    until curl -s http://localhost:3000/api/health -o /dev/null; do
        echo Waiting for grafana ...
        sleep 1
    done
    echo "Grafana is up!"
}

function teardown_stack
{
    log "DEPLOY" "Tearing down Stack ..."
    execute_command "cd ../infra"
    docker-compose -f docker-compose.yml down
    log "DEPLOY" "Stack teardown complete."
}

# --------------------------
# Main
# --------------------------

launch_mode="${1:-}"
shift

shift $((OPTIND -1))

case "${launch_mode}" in
    (start)
        deploy_stack
        ;;
    (stop)
        teardown_stack
        ;;
    (restart)
        teardown_stack
        deploy_stack
        ;;
    (*)
        log "MAIN" "Please choose a valid launch mode: start, stop, restart"
        exit 1
        ;;
esac
