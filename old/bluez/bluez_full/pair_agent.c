#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <dbus/dbus.h>

#define BLUEZ_SERVICE "org.bluez"
#define AGENT_PATH "/org/bluez/autopair"
#define AGENT_INTERFACE "org.bluez.Agent1"

static int running = 1;

// Handle Release method
DBusHandlerResult agent_release(DBusConnection *conn, DBusMessage *msg) {
    printf("Agent released\n");
    running = 0;
    return dbus_message_new_method_return(msg) ? DBUS_HANDLER_RESULT_HANDLED : DBUS_HANDLER_RESULT_NOT_YET_HANDLED;
}

// Handle RequestPinCode method - auto-accept with default PIN
DBusHandlerResult agent_request_pin(DBusConnection *conn, DBusMessage *msg) {
    const char *device;
    dbus_message_get_args(msg, NULL, DBUS_TYPE_OBJECT_PATH, &device, DBUS_TYPE_INVALID);
    printf("RequestPinCode for %s - returning 0000\n", device);

    DBusMessage *reply = dbus_message_new_method_return(msg);
    const char *pin = "0000";
    dbus_message_append_args(reply, DBUS_TYPE_STRING, &pin, DBUS_TYPE_INVALID);
    dbus_connection_send(conn, reply, NULL);
    dbus_message_unref(reply);
    return DBUS_HANDLER_RESULT_HANDLED;
}

// Handle RequestPasskey method - auto-accept with passkey 0
DBusHandlerResult agent_request_passkey(DBusConnection *conn, DBusMessage *msg) {
    const char *device;
    dbus_message_get_args(msg, NULL, DBUS_TYPE_OBJECT_PATH, &device, DBUS_TYPE_INVALID);
    printf("RequestPasskey for %s - returning 0\n", device);

    DBusMessage *reply = dbus_message_new_method_return(msg);
    dbus_uint32_t passkey = 0;
    dbus_message_append_args(reply, DBUS_TYPE_UINT32, &passkey, DBUS_TYPE_INVALID);
    dbus_connection_send(conn, reply, NULL);
    dbus_message_unref(reply);
    return DBUS_HANDLER_RESULT_HANDLED;
}

// Handle RequestConfirmation method - auto-accept
DBusHandlerResult agent_request_confirmation(DBusConnection *conn, DBusMessage *msg) {
    const char *device;
    dbus_uint32_t passkey;
    dbus_message_get_args(msg, NULL, DBUS_TYPE_OBJECT_PATH, &device, DBUS_TYPE_UINT32, &passkey, DBUS_TYPE_INVALID);
    printf("RequestConfirmation for %s passkey %06u - auto-accepting\n", device, passkey);

    DBusMessage *reply = dbus_message_new_method_return(msg);
    dbus_connection_send(conn, reply, NULL);
    dbus_message_unref(reply);
    return DBUS_HANDLER_RESULT_HANDLED;
}

// Handle RequestAuthorization method - auto-accept
DBusHandlerResult agent_request_authorization(DBusConnection *conn, DBusMessage *msg) {
    const char *device;
    dbus_message_get_args(msg, NULL, DBUS_TYPE_OBJECT_PATH, &device, DBUS_TYPE_INVALID);
    printf("RequestAuthorization for %s - auto-accepting\n", device);

    DBusMessage *reply = dbus_message_new_method_return(msg);
    dbus_connection_send(conn, reply, NULL);
    dbus_message_unref(reply);
    return DBUS_HANDLER_RESULT_HANDLED;
}

// Handle AuthorizeService method - auto-accept
DBusHandlerResult agent_authorize_service(DBusConnection *conn, DBusMessage *msg) {
    const char *device, *uuid;
    dbus_message_get_args(msg, NULL, DBUS_TYPE_OBJECT_PATH, &device, DBUS_TYPE_STRING, &uuid, DBUS_TYPE_INVALID);
    printf("AuthorizeService for %s uuid %s - auto-accepting\n", device, uuid);

    DBusMessage *reply = dbus_message_new_method_return(msg);
    dbus_connection_send(conn, reply, NULL);
    dbus_message_unref(reply);
    return DBUS_HANDLER_RESULT_HANDLED;
}

// Handle Cancel method
DBusHandlerResult agent_cancel(DBusConnection *conn, DBusMessage *msg) {
    printf("Pairing request canceled\n");
    DBusMessage *reply = dbus_message_new_method_return(msg);
    dbus_connection_send(conn, reply, NULL);
    dbus_message_unref(reply);
    return DBUS_HANDLER_RESULT_HANDLED;
}

// Message handler
DBusHandlerResult message_handler(DBusConnection *conn, DBusMessage *msg, void *data) {
    const char *member = dbus_message_get_member(msg);
    const char *interface = dbus_message_get_interface(msg);

    if (!interface || strcmp(interface, AGENT_INTERFACE) != 0)
        return DBUS_HANDLER_RESULT_NOT_YET_HANDLED;

    if (strcmp(member, "Release") == 0)
        return agent_release(conn, msg);
    else if (strcmp(member, "RequestPinCode") == 0)
        return agent_request_pin(conn, msg);
    else if (strcmp(member, "RequestPasskey") == 0)
        return agent_request_passkey(conn, msg);
    else if (strcmp(member, "RequestConfirmation") == 0)
        return agent_request_confirmation(conn, msg);
    else if (strcmp(member, "RequestAuthorization") == 0)
        return agent_request_authorization(conn, msg);
    else if (strcmp(member, "AuthorizeService") == 0)
        return agent_authorize_service(conn, msg);
    else if (strcmp(member, "Cancel") == 0)
        return agent_cancel(conn, msg);

    return DBUS_HANDLER_RESULT_NOT_YET_HANDLED;
}

int main() {
    DBusError err;
    DBusConnection *conn;
    DBusMessage *msg, *reply;
    DBusMessageIter args;

    dbus_error_init(&err);

    // Connect to system bus
    conn = dbus_bus_get(DBUS_BUS_SYSTEM, &err);
    if (dbus_error_is_set(&err)) {
        fprintf(stderr, "Connection Error: %s\n", err.message);
        dbus_error_free(&err);
        return 1;
    }

    // Register object path
    DBusObjectPathVTable vtable = { .message_function = message_handler };
    if (!dbus_connection_register_object_path(conn, AGENT_PATH, &vtable, NULL)) {
        fprintf(stderr, "Failed to register object path\n");
        return 1;
    }

    // Register agent with bluetoothd
    msg = dbus_message_new_method_call(BLUEZ_SERVICE, "/org/bluez", "org.bluez.AgentManager1", "RegisterAgent");
    dbus_message_iter_init_append(msg, &args);
    const char *path = AGENT_PATH;
    const char *capability = "NoInputNoOutput";
    dbus_message_iter_append_basic(&args, DBUS_TYPE_OBJECT_PATH, &path);
    dbus_message_iter_append_basic(&args, DBUS_TYPE_STRING, &capability);

    reply = dbus_connection_send_with_reply_and_block(conn, msg, 1000, &err);
    dbus_message_unref(msg);

    if (dbus_error_is_set(&err)) {
        fprintf(stderr, "RegisterAgent Error: %s\n", err.message);
        dbus_error_free(&err);
        return 1;
    }
    if (reply) dbus_message_unref(reply);

    printf("Agent registered successfully\n");

    // Request default agent
    msg = dbus_message_new_method_call(BLUEZ_SERVICE, "/org/bluez", "org.bluez.AgentManager1", "RequestDefaultAgent");
    dbus_message_iter_init_append(msg, &args);
    dbus_message_iter_append_basic(&args, DBUS_TYPE_OBJECT_PATH, &path);

    reply = dbus_connection_send_with_reply_and_block(conn, msg, 1000, &err);
    dbus_message_unref(msg);

    if (dbus_error_is_set(&err)) {
        fprintf(stderr, "RequestDefaultAgent Error: %s\n", err.message);
        dbus_error_free(&err);
    }
    if (reply) dbus_message_unref(reply);

    printf("Agent set as default - ready to handle pairing requests\n");

    // Main loop
    while (running) {
        dbus_connection_read_write_dispatch(conn, 1000);
    }

    // Unregister agent
    msg = dbus_message_new_method_call(BLUEZ_SERVICE, "/org/bluez", "org.bluez.AgentManager1", "UnregisterAgent");
    dbus_message_iter_init_append(msg, &args);
    dbus_message_iter_append_basic(&args, DBUS_TYPE_OBJECT_PATH, &path);
    dbus_connection_send_with_reply_and_block(conn, msg, 1000, NULL);
    dbus_message_unref(msg);

    dbus_connection_unref(conn);
    return 0;
}
