import ast
import itertools
import sully
import types

# The constants below are used when trying to identify Redis client objects
REDIS_METHODS = set(['append', 'blpop', 'brpop', 'brpoplpush', 'decr',
                     'delete', 'execute', 'exists', 'expire', 'expireat',
                     'get', 'getbit', 'getset', 'hdel', 'hget', 'hgetall',
                     'hincrby', 'hkeys', 'hlen', 'hmget', 'hmset', 'hset',
                     'hsetnx', 'hvals', 'incr', 'lindex', 'linsert', 'llen',
                     'lpop', 'lpush', 'lpushnx', 'lrange', 'lrem', 'lset',
                     'ltrim', 'mget', 'move', 'mset', 'mset', 'msetnx',
                     'persist', 'publish', 'randomkey', 'rename', 'renamenx',
                     'rpop', 'rpoplpush', 'rpush', 'rpushx', 'sadd', 'scard',
                     'sdiff', 'sdiffstore', 'set', 'setbit', 'setex', 'setnx',
                     'setrange', 'sinter', 'sinterstore', 'sismember',
                     'smembers', 'smove', 'sort', 'spop', 'srandmember',
                     'srem', 'strlen', 'substr', 'sunion', 'sunionstore',
                     'ttl', 'zadd', 'zcard', 'zincrby', 'zinterstore',
                     'zrange', 'zrangebyscore', 'zrank', 'zrem',
                     'zremrangebyrank', 'zrevrange', 'zrevrangebyscore',
                     'zrevrank', 'zrevscore', 'zunionstore'])
REDIS_METHOD_COUNT = 2
REDIS_METHOD_PCT = 0.8

# Identify objects likely to be used to access Redis in the code
def identify_redis_objs(func):
    redis_func_objs = []
    nonredis_func_objs = []
    func_ast = sully.get_func_ast(func)
    node_walkers = (ast.walk(func_node) for func_node in func_ast)
    for node in itertools.chain.from_iterable(node_walkers):
        # Skip any nodes which are not function calls on objects
        if not (isinstance(node, ast.Call) and
                isinstance(node.func, ast.Attribute)):
            continue

        # Record all function calls
        if node.func.attr in REDIS_METHODS:
            redis_func_objs.append(node.func.value)
        else:
            nonredis_func_objs.append(node.func.value)

    # Loop through all the found function objects to pick
    # out the ones we deem to represent Redis interfaces
    redis_objs = []
    while len(redis_func_objs) > 0:
        obj = redis_func_objs.pop()

        # Remove all call nodes matching this object
        redis_before = len(redis_func_objs) + 1
        redis_func_objs = [obj2 for obj2 in redis_func_objs
                if not sully.nodes_equal(obj, obj2)]

        nonredis_before = len(nonredis_func_objs)
        nonredis_func_objs = [obj2 for obj2 in nonredis_func_objs
                if not sully.nodes_equal(obj, obj2)]

        # If the object meets a threshold of calls for the object
        # and a certain percentage of all calls match, record it
        redis_calls = redis_before - len(redis_func_objs)
        nonredis_calls = nonredis_before - len(nonredis_func_objs)
        if redis_calls >= REDIS_METHOD_COUNT and \
           (redis_calls * 1.0 /
                   (redis_calls + nonredis_calls)) >= REDIS_METHOD_PCT:
           redis_objs.append(obj)

    return redis_objs

# Identify functions in a class or module which use Redis
def identify_redis_funcs(cls_or_mod):
    redis_funcs = {}

    for obj in dir(cls_or_mod):
        # Skip things which look private
        if obj.startswith('_'):
            continue

        val = getattr(cls_or_mod, obj)

        if isinstance(val, (types.ClassType)):
            # Recursively check all classes
            class_funcs = identify_redis_funcs(cls_or_mod)
            redis_funcs.update(class_funcs)
        elif isinstance(val, (types.FunctionType, types.MethodType)):
            # Identify Redis objects within the function
            objs = identify_redis_objs(val)
            if len(objs) > 0:
                redis_funcs[val] = objs

    return redis_funcs