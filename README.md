# Nates' Anti Nuke Bot

An anti nuke bot; self explanitory.

## Usage

### Setting log channel

Use this command to set the channel the bot should send logs to.

```
nan!setlogchannel <#channel>
```

### Adding rules

When x action (trigger) is performed in y time performs z punishment.

```
nan!addrule <name> <trigger> <amount> <time> <punishment>
```

**Availible triggers**
1. kick
2. mute
3. ban

You can also multiple triggers at once using the semicolomn (;) or pipe (|) as a separator. For example ban;kick or ban|kick will trigger on both bans and kicks.

### Removing rules

Remove an existing rule.

```
nan!removerule <name|all>
```

### Additional settings

**Take action on bots (boolean) (default:true)**: to also trigger when a bot perms an action. **HEAVILY RECOMENDED** 