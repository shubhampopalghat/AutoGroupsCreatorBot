# Save this file as BigBotFinal.py
import asyncio
import random
import json
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.errors.rpcerrorlist import FloodWaitError

API_ID = 21724
API_HASH = "3e031518f826d2524851486022e34273"

async def account_worker(account_info, groups_to_create, messages_to_send, delay, progress_queue):
    session_path = account_info['session_path']
    account_details = "Could not log in."
    total_created_this_run = 0
    output_filename = f"{account_info.get('phone', 'session').replace('+', '')}_links.txt"
    open(output_filename, 'w').close()

    try:
        async with TelegramClient(session_path, API_ID, API_HASH) as client:
            me = await client.get_me()
            account_details = (
                f"👤 **Name:** {me.first_name} {me.last_name or ''}\n"
                f"🔖 **Username:** @{me.username or 'N/A'}\n"
                f"🆔 **ID:** `{me.id}`"
            )
            for i in range(groups_to_create):
                group_title = f"{random.choice(['Golden', 'Silent', 'Hidden'])} {random.choice(['Oasis', 'Sanctuary', 'Valley'])} {random.randint(100, 999)}"
                try:
                    result = await client(CreateChannelRequest(title=group_title, about="Automated group", megagroup=True))
                    new_group = result.chats[0]
                    await asyncio.sleep(3)
                    invite_result = await client(ExportChatInviteRequest(new_group.id))
                    with open(output_filename, 'a') as f: f.write(f"{invite_result.link}\n")
                    await asyncio.sleep(delay)
                    for j, msg in enumerate(messages_to_send):
                        await client.send_message(new_group.id, msg)
                        if j < len(messages_to_send) - 1: await asyncio.sleep(delay)
                    total_created_this_run += 1
                    progress_queue.put(1)
                except FloodWaitError as fwe:
                    await asyncio.sleep(fwe.seconds)
                except Exception:
                    continue
    except Exception as e:
        print(f"FATAL ERROR for {account_info.get('phone')}: {e}")
    finally:
        return {
            "created_count": total_created_this_run,
            "account_details": account_details,
            "output_file": output_filename if total_created_this_run > 0 else None
        }

async def run_group_creation_process(account_config, total_groups, msgs_per_group, delay, messages, progress_queue):
    results = await asyncio.gather(account_worker(account_config, total_groups, messages[:msgs_per_group], delay, progress_queue))
    progress_queue.put(f"DONE:{json.dumps(results)}")