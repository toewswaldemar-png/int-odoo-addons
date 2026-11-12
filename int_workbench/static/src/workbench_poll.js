import { onWillUnmount, useState } from "@odoo/owl";

/**
 * Reads one route of the controller service now and then every `every` ms, and keeps the last answer.
 * `getClient` is asked at every read, so a component that gets a new client reads from the new service.
 * The timer stops with the component; a read that is overtaken by a newer one is dropped.
 */
export function usePoll(getClient) {
    // errorStatus: the HTTP status of the failed read (401: the service wants a sign-in), 0 if it could not be reached
    const state = useState({ data: null, error: null, errorStatus: null, loading: false });
    let path = null;
    let watched = null; // the client of the last watch: another one means another service, the old answer is not its answer
    let every = 2500;
    let timer = null;
    let controller = null;
    let latest = 0;
    let alive = true;

    async function run() {
        clearTimeout(timer);
        const client = getClient();
        if (!alive || !path || !client) {
            return;
        }
        if (typeof document !== "undefined" && document.hidden) {
            // a tab that nobody sees does not read: the service is not asked for reports for nobody
            timer = setTimeout(run, every);
            return;
        }
        const mine = ++latest;
        controller?.abort();
        controller = new AbortController();
        try {
            const data = await client.get(path, controller.signal);
            if (alive && mine === latest) {
                state.data = data;
                state.error = null;
                state.errorStatus = null;
            }
        } catch (error) {
            if (error.name === "AbortError") {
                return;
            }
            if (alive && mine === latest) {
                state.error = error.message;
                state.errorStatus = error.status ?? null;
            }
        }
        if (alive && mine === latest) {
            state.loading = false;
            timer = setTimeout(run, every);
        }
    }

    onWillUnmount(() => {
        alive = false;
        clearTimeout(timer);
        controller?.abort();
    });

    return {
        state,
        /** Start reading `newPath` (and forget the answer of the old one). */
        watch(newPath, interval = 2500) {
            const client = getClient();
            if (newPath !== path || client !== watched) {
                state.data = null;
                state.error = null;
                state.errorStatus = null;
            }
            path = newPath;
            watched = client;
            every = interval;
            state.loading = true;
            return run();
        },
        /** Read again now, for example after a write. */
        refresh: run,
    };
}
