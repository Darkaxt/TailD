package com.tailscale.ipn.taild;

// A fixed app/UID policy boundary, never a shell or generic Binder proxy.
interface IAppAccessService {
    String inspect(int profile) = 0;
    String apply(String request) = 1;
    void destroy() = 16777114;
}
