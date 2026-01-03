-- mGBA Lua TCP Server (Persistent)
local port = 8888
console:log("Initializing Server on port " .. port)

-- Use the global socket provided by mGBA
local server = socket.bind(nil, port)
local client = nil

if server then
    server:listen() -- Crucial: this makes the port appear in ss -l
    console:log("Server listening...")
else
    console:log("Failed to bind server.")
end

function tick()
    if not server then return end

    -- 1. Manage Connection
    if not client then
        client = server:accept()
        if client then
            console:log("Client connected!")
        end
    end

    -- 2. Handle Persistent Communication
    if client then
        -- We check if Python sent exactly 1 byte (the 'request' signal)
        -- If mGBA's receive is blocking, this will only run when Python pings
        local msg = client:receive(1)

        if msg == "\1" then
            local wram = emu.memory.wram
            local buf = {}
            
            -- Dumping 32KB
            for i = 0, 0x7FFF do
                table.insert(buf, string.char(wram:read8(i)))
            end
            
            local payload = table.concat(buf)
            local success = client:send(payload)
            
            if not success then
                console:log("Send failed. Closing client.")
                client:close()
                client = nil
            end
        elseif msg == nil and client then
            -- This usually means the client disconnected
            -- console:log("Client disconnected.")
            -- client:close()
            -- client = nil
        end
    end
end

callbacks:add("frame", tick)
