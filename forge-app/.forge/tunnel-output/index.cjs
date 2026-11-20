/******/ (() => { // webpackBootstrap
/******/ 	var __webpack_modules__ = ({

/***/ 2167
(__unused_webpack_module, exports) {

"use strict";
var __webpack_unused_export__;

__webpack_unused_export__ = ({ value: true });
exports.getInstallationAri = exports.getEnvironmentAri = exports.getAppAri = void 0;
const getAppAri = (appId) => ({
    appId,
    toString: () => `ari:cloud:ecosystem::app/${appId}`,
    toJSON: () => `ari:cloud:ecosystem::app/${appId}`
});
exports.getAppAri = getAppAri;
const getEnvironmentAri = (appId, environmentId) => ({
    environmentId,
    toString: () => `ari:cloud:ecosystem::environment/${appId}/${environmentId}`,
    toJSON: () => `ari:cloud:ecosystem::environment/${appId}/${environmentId}`
});
exports.getEnvironmentAri = getEnvironmentAri;
const getInstallationAri = (installationId) => ({
    installationId,
    toString: () => `ari:cloud:ecosystem::installation/${installationId}`,
    toJSON: () => `ari:cloud:ecosystem::installation/${installationId}`
});
exports.getInstallationAri = getInstallationAri;


/***/ },

/***/ 972
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";
var __webpack_unused_export__;

__webpack_unused_export__ = ({ value: true });
exports.invokeRemote = invokeRemote;
exports.invokeService = invokeService;
const errors_1 = __webpack_require__(9742);
const fetch_1 = __webpack_require__(8265);
var InvokeType;
(function (InvokeType) {
    InvokeType["REMOTE"] = "Remote";
    InvokeType["CONTAINER"] = "Service";
})(InvokeType || (InvokeType = {}));
async function invokeRemote(remoteKey, options) {
    return invokeEndpoint(remoteKey, options, InvokeType.REMOTE);
}
async function invokeService(serviceKey, options) {
    return invokeEndpoint(serviceKey, options, InvokeType.CONTAINER);
}
async function invokeEndpoint(key, options, type) {
    const { path, ...fetchOptions } = options;
    if (!key) {
        throw new Error(`Missing ${type.toLowerCase()} key provided to invoke${type}`);
    }
    if (!path) {
        throw new Error(`Missing or empty path provided to invoke${type}`);
    }
    const response = await global.__forge_fetch__(constructInvokePayload(key, type), path, fetchOptions);
    handleResponseErrors(response, key);
    return response;
}
function constructInvokePayload(key, type) {
    switch (type) {
        case InvokeType.REMOTE:
            return {
                type: 'frc',
                remote: key
            };
        case InvokeType.CONTAINER:
            return {
                type: 'fcc',
                service: key
            };
    }
}
function handleResponseErrors(response, key) {
    const forgeProxyError = (0, fetch_1.getForgeProxyError)(response);
    if (forgeProxyError === 'INVALID_SERVICE_KEY') {
        throw new errors_1.InvalidContainerServiceError(`Invalid service key provided: "${key}"`, key);
    }
    else if (forgeProxyError === 'INVALID_REMOTE') {
        throw new errors_1.InvalidRemoteError(`Invalid remote key provided: "${key}"`, key);
    }
    (0, fetch_1.handleProxyResponseErrors)(response);
}


/***/ },

/***/ 9742
(__unused_webpack_module, exports) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.ApiNotReadyError = exports.SendEmailError = exports.ProxyRequestError = exports.InvalidContainerServiceError = exports.InvalidRemoteError = exports.NeedsAuthenticationError = exports.InvalidWorkspaceRequestedError = exports.RequestProductNotAllowedError = exports.ProductEndpointNotAllowedError = exports.ExternalEndpointNotAllowedError = exports.NotAllowedError = exports.FetchError = exports.HttpError = exports.API_NOT_READY_ERR = exports.SEND_EMAIL_ERR = exports.PROXY_ERR = exports.INVALID_CONTAINER_SERVICE_ERR = exports.INVALID_REMOTE_ERR = exports.NEEDS_AUTHENTICATION_ERR = exports.FUNCTION_FETCH_ERR = exports.REQUEST_EGRESS_ALLOWLIST_ERR = exports.FUNCTION_ERR = void 0;
exports.isForgePlatformError = isForgePlatformError;
exports.isHostedCodeError = isHostedCodeError;
exports.isExpectedError = isExpectedError;
exports.FUNCTION_ERR = 'FUNCTION_ERR';
exports.REQUEST_EGRESS_ALLOWLIST_ERR = 'REQUEST_EGRESS_ALLOWLIST_ERR';
exports.FUNCTION_FETCH_ERR = 'FUNCTION_FETCH_ERR';
exports.NEEDS_AUTHENTICATION_ERR = 'NEEDS_AUTHENTICATION_ERR';
exports.INVALID_REMOTE_ERR = 'INVALID_REMOTE_ERR';
exports.INVALID_CONTAINER_SERVICE_ERR = 'INVALID_CONTAINER_SERVICE_ERR';
exports.PROXY_ERR = 'PROXY_ERR';
exports.SEND_EMAIL_ERR = 'SEND_EMAIL_ERR';
exports.API_NOT_READY_ERR = 'API_NOT_READY_ERR';
function isForgePlatformError(err) {
    return [
        exports.REQUEST_EGRESS_ALLOWLIST_ERR,
        exports.FUNCTION_FETCH_ERR,
        exports.NEEDS_AUTHENTICATION_ERR,
        exports.PROXY_ERR,
        exports.SEND_EMAIL_ERR,
        exports.API_NOT_READY_ERR
    ].includes(err.name);
}
function isHostedCodeError(err) {
    return [
        exports.FUNCTION_ERR,
        exports.REQUEST_EGRESS_ALLOWLIST_ERR,
        exports.FUNCTION_FETCH_ERR,
        exports.NEEDS_AUTHENTICATION_ERR,
        exports.SEND_EMAIL_ERR
    ].includes(typeof err === 'string' ? err : err.name);
}
function isExpectedError(err) {
    return err.name === exports.NEEDS_AUTHENTICATION_ERR && !!err.options?.isExpectedError;
}
class HttpError extends Error {
    status;
    constructor(message) {
        super(message);
    }
}
exports.HttpError = HttpError;
class FetchError extends Error {
    constructor(cause) {
        super(cause);
        this.stack = undefined;
        this.name = exports.FUNCTION_FETCH_ERR;
    }
}
exports.FetchError = FetchError;
class NotAllowedError extends HttpError {
    constructor(message) {
        super(message);
        this.stack = undefined;
        this.name = exports.REQUEST_EGRESS_ALLOWLIST_ERR;
        this.status = 403;
    }
}
exports.NotAllowedError = NotAllowedError;
class ExternalEndpointNotAllowedError extends NotAllowedError {
    constructor(failedURL) {
        super(`URL not included in the external fetch backend permissions: ${failedURL}. Visit go.atlassian.com/forge-egress for more information.`);
    }
}
exports.ExternalEndpointNotAllowedError = ExternalEndpointNotAllowedError;
class ProductEndpointNotAllowedError extends NotAllowedError {
    constructor(failedURL) {
        super(`URL not allowed: ${failedURL}.`);
    }
}
exports.ProductEndpointNotAllowedError = ProductEndpointNotAllowedError;
class RequestProductNotAllowedError extends NotAllowedError {
    constructor(requestedProduct, invocationProduct) {
        super(`Request ${requestedProduct} is not allowed from ${invocationProduct} context.`);
    }
}
exports.RequestProductNotAllowedError = RequestProductNotAllowedError;
class InvalidWorkspaceRequestedError extends NotAllowedError {
    constructor(failedURL) {
        super(`Invalid workspace requested in URL: ${failedURL}.`);
    }
}
exports.InvalidWorkspaceRequestedError = InvalidWorkspaceRequestedError;
class NeedsAuthenticationError extends HttpError {
    serviceKey;
    options;
    constructor(error, serviceKey, options) {
        super(error);
        this.serviceKey = serviceKey;
        this.options = options;
        this.stack = undefined;
        this.name = exports.NEEDS_AUTHENTICATION_ERR;
        this.status = 401;
    }
}
exports.NeedsAuthenticationError = NeedsAuthenticationError;
class InvalidRemoteError extends HttpError {
    remoteKey;
    constructor(error, remoteKey) {
        super(error);
        this.remoteKey = remoteKey;
        this.name = exports.INVALID_REMOTE_ERR;
        this.status = 400;
    }
}
exports.InvalidRemoteError = InvalidRemoteError;
class InvalidContainerServiceError extends HttpError {
    serviceKey;
    constructor(error, serviceKey) {
        super(error);
        this.serviceKey = serviceKey;
        this.name = exports.INVALID_CONTAINER_SERVICE_ERR;
        this.status = 400;
    }
}
exports.InvalidContainerServiceError = InvalidContainerServiceError;
class ProxyRequestError extends HttpError {
    status;
    errorCode;
    constructor(status, errorCode) {
        super(`Forge platform failed to process runtime HTTP request - ${status} - ${errorCode}`);
        this.status = status;
        this.errorCode = errorCode;
        this.name = exports.PROXY_ERR;
    }
}
exports.ProxyRequestError = ProxyRequestError;
class SendEmailError extends HttpError {
    status;
    errorCode;
    code;
    responseCode;
    command;
    constructor(status, errorCode, code, responseCode, command) {
        super(`Failed to send email with error code: ${errorCode}`);
        this.status = status;
        this.errorCode = errorCode;
        this.code = code;
        this.responseCode = responseCode;
        this.command = command;
        this.name = exports.SEND_EMAIL_ERR;
    }
}
exports.SendEmailError = SendEmailError;
class ApiNotReadyError extends Error {
    constructor(message = 'Forge API currently not available') {
        super(message);
        this.name = exports.API_NOT_READY_ERR;
    }
}
exports.ApiNotReadyError = ApiNotReadyError;


/***/ },

/***/ 8265
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";
var __webpack_unused_export__;

__webpack_unused_export__ = ({ value: true });
exports.__requestAtlassianAsUser = exports.__requestAtlassianAsApp = exports.XB = exports.gk = exports.Yk = exports.handleProxyResponseErrors = exports.getForgeProxyError = void 0;
exports.__fetchProduct = __fetchProduct;
__webpack_unused_export__ = fetchRemote;
exports.getFetchAPI = getFetchAPI;
const ari_1 = __webpack_require__(3752);
const safeUrl_1 = __webpack_require__(1228);
const errors_1 = __webpack_require__(9742);
const runtime_1 = __webpack_require__(5429);
const CONTEXT_PRODUCTS = ['jira', 'confluence'];
async function wrapInMetrics(options, cb) {
    const metrics = (0, runtime_1.__getRuntime)().metrics;
    metrics.counter(options.name, options.tags).incr();
    const timer = metrics.timing(options.name, options.tags).measure();
    try {
        return await cb();
    }
    finally {
        timer.stop();
    }
}
function __fetchProduct(args) {
    return async (path, init) => {
        const response = await global.__forge_fetch__({
            type: args.type,
            provider: args.provider,
            accountId: args.accountId,
            ...(args.remote ? { remote: args.remote } : {}),
            ...(args.contextAri ? { contextAri: args.contextAri } : {})
        }, path, init);
        (0, exports.handleProxyResponseErrors)(response);
        return response;
    };
}
function fetchRemote(args) {
    return async (path, init) => {
        const response = await global.__forge_fetch__({
            type: 'tpp',
            provider: args.provider,
            remote: args.remote,
            accountId: args.account
        }, path, init);
        (0, exports.handleProxyResponseErrors)(response);
        return response;
    };
}
function getDefaultRemote(provider) {
    const externalAuthProvider = findExternalAuthProviderConfigOrThrow(provider);
    if (!externalAuthProvider.remotes.length) {
        throw new Error(`Missing remote config for provider ${provider}`);
    }
    return externalAuthProvider.remotes[0].key;
}
function findExternalAuthProviderConfigOrThrow(provider) {
    const { externalAuth } = (0, runtime_1.__getRuntime)();
    const externalAuthProvider = externalAuth?.find((externalAuthMetaData) => {
        return externalAuthMetaData.service === provider;
    });
    if (!externalAuthProvider) {
        throw new Error(`Bad provider or missing config for provider ${provider}`);
    }
    return externalAuthProvider;
}
const ATLASSIAN_TOKEN_SERVICE_KEY = 'atlassian-token-service-key';
const getForgeProxyError = (response) => response.headers.get('forge-proxy-error');
exports.getForgeProxyError = getForgeProxyError;
const handleProxyResponseErrors = (response) => {
    const errorReason = (0, exports.getForgeProxyError)(response);
    if (errorReason) {
        if (errorReason === 'NEEDS_AUTHENTICATION_ERR') {
            throw new errors_1.NeedsAuthenticationError('Authentication Required', ATLASSIAN_TOKEN_SERVICE_KEY);
        }
        throw new errors_1.ProxyRequestError(response.status, errorReason);
    }
};
exports.handleProxyResponseErrors = handleProxyResponseErrors;
function lazyThrowNeedsAuthenticationError(serviceKey) {
    return async (scopes) => wrapInMetrics({ name: 'api.asUser.withProvider.requestCredentials', tags: { passingScopes: String(!!scopes) } }, async () => {
        throw new errors_1.NeedsAuthenticationError('Authentication Required', serviceKey, { scopes, isExpectedError: true });
    });
}
function buildExternalAuthAccountsInfo(provider, remote) {
    const { accounts } = findExternalAuthProviderConfigOrThrow(provider);
    const buildAccountModel = (account) => {
        const { externalAccountId: id, ...rest } = account;
        return { ...rest, id };
    };
    const buildExternalAuthAccountMethods = (account, outboundAuthAccountId) => ({
        hasCredentials: async (scopes) => wrapInMetrics({ name: 'api.asUser.withProvider.hasCredentials', tags: { passingScopes: String(!!scopes) } }, async () => !scopes || scopes.every((scope) => account.scopes.includes(scope))),
        requestCredentials: lazyThrowNeedsAuthenticationError(provider),
        getAccount: async () => wrapInMetrics({ name: 'api.asUser.withProvider.getAccount' }, async () => account),
        fetch: wrapWithRouteUnwrapper(fetchRemote({ provider, remote: remote ?? getDefaultRemote(provider), account: outboundAuthAccountId }))
    });
    return accounts.map((account) => {
        const authAccount = buildAccountModel(account);
        return {
            account: authAccount,
            methods: buildExternalAuthAccountMethods(authAccount, account.id)
        };
    });
}
const throwNotImplementedError = () => {
    throw new Error('not implemented');
};
const withProvider = (provider, remote) => {
    const accountsInfo = buildExternalAuthAccountsInfo(provider, remote);
    const defaultAccountInfo = accountsInfo.length ? accountsInfo[0] : undefined;
    const lazyThrowNoValidCredentialsError = () => {
        return (url) => {
            throw new Error(`Fetch failed for ${remote ? `remote '${remote}', ` : ''}provider '${provider}', path '${url}' no credentials previously requested`);
        };
    };
    return {
        hasCredentials: async (scopes) => {
            return defaultAccountInfo
                ? await defaultAccountInfo.methods.hasCredentials(scopes)
                : await wrapInMetrics({ name: 'api.asUser.withProvider.hasCredentials', tags: { passingScopes: String(!!scopes) } }, async () => false);
        },
        getAccount: async () => wrapInMetrics({ name: 'api.asUser.withProvider.getAccount' }, async () => {
            return defaultAccountInfo ? defaultAccountInfo.account : undefined;
        }),
        requestCredentials: lazyThrowNeedsAuthenticationError(provider),
        listCredentials: throwNotImplementedError,
        listAccounts: async () => wrapInMetrics({ name: 'api.asUser.withProvider.listAccounts' }, async () => {
            return accountsInfo.map(({ account }) => account);
        }),
        asAccount: (externalAccountId) => {
            const accountInfo = accountsInfo.find(({ account }) => account.id === externalAccountId);
            if (!accountInfo) {
                throw new Error(`No account with ID ${externalAccountId} found for provider ${provider}`);
            }
            return accountInfo.methods;
        },
        fetch: defaultAccountInfo ? defaultAccountInfo.methods.fetch : lazyThrowNoValidCredentialsError()
    };
};
const withContext = (provider, accountId) => {
    const isContextProduct = (resourceOwner) => CONTEXT_PRODUCTS.includes(resourceOwner);
    const parseContextAri = (contextAri) => {
        try {
            return ari_1.AnyAri.parse(contextAri);
        }
        catch {
            throw new Error(`Invalid context ID: '${contextAri}'`);
        }
    };
    return (contextAri) => {
        const { resourceOwner } = parseContextAri(contextAri);
        if (!isContextProduct(resourceOwner)) {
            throw new Error(`Unsupported context resource owner '${resourceOwner}' for withContext. Only ${CONTEXT_PRODUCTS.join(', ')} are supported.`);
        }
        const makeRequest = (product) => {
            const requestProduct = wrapRequestProduct(__fetchProduct({ provider, contextAri, type: 'fpp', accountId }));
            return async (path, init) => {
                if (resourceOwner !== product) {
                    throw new Error(`Context resource owner '${resourceOwner}' does not match request${product.charAt(0).toUpperCase()}${product.slice(1)}`);
                }
                return requestProduct(path, init);
            };
        };
        return {
            requestJira: makeRequest('jira'),
            requestConfluence: makeRequest('confluence')
        };
    };
};
const wrapWithRouteUnwrapper = (fetch) => (path, init) => {
    const stringPath = (0, safeUrl_1.isRoute)(path) ? path.value : path;
    return fetch(stringPath, init);
};
const wrapRequestProduct = (requestProduct) => (path, init) => {
    const safeUrl = (0, safeUrl_1.requireSafeUrl)(path);
    return requestProduct(safeUrl.value, init);
};
const wrapRequestGraph = (requestGraphApi) => (query, variables, headers = {}) => requestGraphApi('/graphql', {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({
        query,
        ...(variables ? { variables } : {})
    })
});
exports.Yk = wrapRequestGraph;
const wrapRequestTeamworkGraph = (requestGraphApi) => (query, variables, operationName, extensions, headers = {}) => {
    const { contextAri } = (0, runtime_1.__getRuntime)();
    const hasQueryContext = Object.keys(headers).some((name) => name.toLowerCase() === 'x-query-context');
    return requestGraphApi('/graphql/twg', {
        method: 'POST',
        headers: {
            ...(contextAri && !hasQueryContext ? { 'X-Query-Context': contextAri } : {}),
            ...headers,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            query,
            ...(variables ? { variables } : {}),
            ...(operationName ? { operationName } : {}),
            ...(extensions ? { extensions } : {})
        })
    });
};
exports.gk = wrapRequestTeamworkGraph;
const wrapRequestConnectedData = (fetch) => (path, init) => {
    const safeUrl = (0, safeUrl_1.requireSafeUrl)(path);
    return fetch(`/connected-data/${safeUrl.value.replace(/^\/+/, '')}`, init);
};
exports.XB = wrapRequestConnectedData;
function getFetchAPI() {
    if (global.fetch === undefined) {
        global.fetch = async () => {
            throw new Error('The fetch function is not available');
        };
    }
    return {
        fetch: wrapWithRouteUnwrapper(fetch),
        requestJira: wrapRequestProduct(__fetchProduct({ provider: 'none', remote: 'jira', type: 'fpp' })),
        requestConfluence: wrapRequestProduct(__fetchProduct({ provider: 'none', remote: 'confluence', type: 'fpp' })),
        requestBitbucket: wrapRequestProduct(__fetchProduct({ provider: 'none', remote: 'bitbucket', type: 'fpp' })),
        asUser: (userId) => ({
            requestJira: wrapRequestProduct(__fetchProduct({ provider: 'user', remote: 'jira', type: 'fpp', accountId: userId })),
            requestConfluence: wrapRequestProduct(__fetchProduct({ provider: 'user', remote: 'confluence', type: 'fpp', accountId: userId })),
            requestBitbucket: wrapRequestProduct(__fetchProduct({ provider: 'user', remote: 'bitbucket', type: 'fpp', accountId: userId })),
            requestGraph: (0, exports.Yk)(__fetchProduct({ provider: 'user', remote: 'stargate', type: 'fpp', accountId: userId })),
            requestTeamworkGraph: (0, exports.gk)(__fetchProduct({ provider: 'user', remote: 'stargate', type: 'fpp', accountId: userId })),
            requestConnectedData: (0, exports.XB)(__fetchProduct({ provider: 'user', remote: 'stargate', type: 'fpp' })),
            requestAtlassian: wrapRequestProduct(__fetchProduct({ provider: 'user', remote: 'stargate', type: 'fpp', accountId: userId })),
            withProvider,
            withContext: withContext('user', userId)
        }),
        asApp: () => ({
            requestJira: wrapRequestProduct(__fetchProduct({ provider: 'app', remote: 'jira', type: 'fpp' })),
            requestConfluence: wrapRequestProduct(__fetchProduct({ provider: 'app', remote: 'confluence', type: 'fpp' })),
            requestBitbucket: wrapRequestProduct(__fetchProduct({ provider: 'app', remote: 'bitbucket', type: 'fpp' })),
            requestGraph: (0, exports.Yk)(__fetchProduct({ provider: 'app', remote: 'stargate', type: 'fpp' })),
            requestConnectedData: (0, exports.XB)(__fetchProduct({ provider: 'app', remote: 'stargate', type: 'fpp' })),
            requestAtlassian: wrapRequestProduct(__fetchProduct({ provider: 'app', remote: 'stargate', type: 'fpp' })),
            withContext: withContext('app')
        })
    };
}
function getRequestStargate(provider) {
    if (provider !== 'app' && provider !== 'user') {
        throw new Error(`Unsupported provider: ${provider}`);
    }
    return __fetchProduct({ provider, remote: 'stargate', type: 'fpp' });
}
exports.__requestAtlassianAsApp = getRequestStargate('app');
exports.__requestAtlassianAsUser = getRequestStargate('user');


/***/ },

/***/ 6613
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.i18n = exports.createTranslationFunction = exports.getTranslations = exports.resetTranslationsCache = void 0;
const i18n_1 = __webpack_require__(4280);
const fs_1 = __webpack_require__(9896);
const path_1 = __webpack_require__(6928);
const runtime_1 = __webpack_require__(5429);
const getI18nBundleFolderPath = () => {
    const { appCodeDir } = (0, runtime_1.__getRuntime)().container;
    return appCodeDir ? [appCodeDir, i18n_1.I18N_BUNDLE_FOLDER_NAME] : [i18n_1.I18N_BUNDLE_FOLDER_NAME];
};
const readLocaleFileContent = async (filePath) => {
    const fileContent = await fs_1.promises.readFile((0, path_1.join)(...getI18nBundleFolderPath(), filePath));
    return JSON.parse(fileContent.toString());
};
const makeResourceAccessorErrorMessage = (message) => {
    if (global.__forge_tunnel__) {
        const cliUpdateWarning = 'To access i18n resources while using `forge tunnel`, please ensure that your Forge CLI is up to date. Run `npm install -g @forge/cli` to update to the latest version.';
        return `${message}\n${cliUpdateWarning}`;
    }
    return message;
};
const resolverResourcesAccessor = {
    getI18nInfoConfig: async () => {
        try {
            const info = (await readLocaleFileContent(i18n_1.I18N_INFO_FILE_NAME));
            return info.config;
        }
        catch (error) {
            throw new i18n_1.TranslationGetterError(makeResourceAccessorErrorMessage('Failed to get i18n info config.'));
        }
    },
    getTranslationResource: async (locale) => {
        try {
            return await readLocaleFileContent(`${locale}.json`);
        }
        catch (error) {
            throw new i18n_1.TranslationGetterError(makeResourceAccessorErrorMessage(`Failed to get translation resource for locale: ${locale}.`));
        }
    }
};
const translationsFunctionCache = new Map();
const translationsGetter = new i18n_1.TranslationsGetter(resolverResourcesAccessor);
const resetTranslationsCache = () => {
    translationsGetter.reset();
    translationsFunctionCache.clear();
};
exports.resetTranslationsCache = resetTranslationsCache;
const getTranslations = async (rawLocale, options = {
    fallback: true
}) => {
    const locale = doEnsureLocale(rawLocale);
    return await translationsGetter.getTranslations(locale, options);
};
exports.getTranslations = getTranslations;
const createTranslationFunction = async (rawLocale) => {
    const locale = doEnsureLocale(rawLocale);
    let translator = translationsFunctionCache.get(locale);
    if (!translator) {
        translator = await createTranslationFunctionImpl(locale);
        translationsFunctionCache.set(locale, translator);
    }
    return translator;
};
exports.createTranslationFunction = createTranslationFunction;
const doEnsureLocale = (rawLocale) => {
    const ensuredLocale = (0, i18n_1.ensureLocale)(rawLocale);
    if (!ensuredLocale) {
        console.warn(`The locale "${rawLocale}" is not supported, defaulting to the default locale.`);
        return rawLocale;
    }
    return ensuredLocale;
};
const createTranslationFunctionImpl = async (locale) => {
    const translator = new i18n_1.Translator(locale, translationsGetter);
    await translator.init();
    return (i18nKey, defaultValue) => translator.translate(i18nKey) ?? defaultValue ?? i18nKey;
};
exports.i18n = {
    createTranslationFunction: exports.createTranslationFunction,
    getTranslations: exports.getTranslations
};


/***/ },

/***/ 3765
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.permissions = exports.canLoadResource = exports.canFetchFrom = exports.hasScope = exports.hasPermission = void 0;
exports.extractUrlString = extractUrlString;
const runtime_1 = __webpack_require__(5429);
const errors_1 = __webpack_require__(9742);
const egress_1 = __webpack_require__(6079);
const RESOURCE_TYPES = (/* unused pure expression or super */ null && (['fonts', 'styles', 'frames', 'images', 'media', 'scripts']));
const FETCH_TYPES = (/* unused pure expression or super */ null && (['backend', 'client']));
function extractUrlString(url) {
    if (typeof url === 'string') {
        return url;
    }
    if ('address' in url) {
        return url.address;
    }
    return url.remote;
}
function wrapInSyncMetrics(options, cb) {
    const metrics = (0, runtime_1.__getRuntime)().metrics;
    metrics.counter(options.name, options.tags).incr();
    return cb();
}
const getMissingScopes = (requiredScopes, currentlyGrantedScopes) => {
    if (!requiredScopes) {
        return undefined;
    }
    if (Array.isArray(requiredScopes) && requiredScopes.length > 0) {
        const currentGrantedScopes = Array.isArray(currentlyGrantedScopes) ? currentlyGrantedScopes : [];
        const missingScopes = requiredScopes.filter((scope) => !currentGrantedScopes.includes(scope));
        if (missingScopes.length > 0) {
            return missingScopes;
        }
    }
    return undefined;
};
const getMissingUrls = (requiredUrls, currentlyGrantedUrls, useCSP) => {
    const allowList = currentlyGrantedUrls.map((url) => extractUrlString(url));
    const egressFilter = new egress_1.EgressFilteringService(allowList);
    const missingUrls = requiredUrls.filter((requiredUrl) => {
        const urlString = extractUrlString(requiredUrl);
        if (useCSP) {
            return !egressFilter.isValidUrlCSP(urlString);
        }
        return !egressFilter.isValidUrl(urlString);
    });
    return missingUrls;
};
const VALID_REQUIREMENT_KEYS = ['scopes', 'external'];
const VALID_EXTERNAL_TYPES = [
    'fetch',
    'fonts',
    'frames',
    'images',
    'media',
    'scripts',
    'styles',
    'configurable'
];
const VALID_FETCH_TYPES = ['backend', 'client'];
const validateKeys = (obj, validKeys) => {
    const validKeysSet = new Set(validKeys);
    const providedKeys = Object.keys(obj);
    const invalidKeys = providedKeys.filter((key) => !validKeysSet.has(key));
    if (invalidKeys.length > 0) {
        throw new Error(`Invalid permission key(s): ${invalidKeys.join(', ')}. ` +
            `Visit https://go.atlassian.com/forge-permissions for more information.`);
    }
};
const validateObjectField = (value, fieldPath) => {
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
        throw new TypeError(`${fieldPath} should be an object, not ${Array.isArray(value) ? 'an array' : `a ${typeof value}`}`);
    }
};
const validateArrayField = (value, fieldPath) => {
    if (value !== undefined && !Array.isArray(value)) {
        throw new TypeError(`${fieldPath} should be an array, not a ${typeof value}`);
    }
};
const validatePermissionRequirements = (requirements) => {
    validateKeys(requirements, VALID_REQUIREMENT_KEYS);
    validateArrayField(requirements.scopes, 'scopes');
    if (requirements.external !== undefined) {
        validateObjectField(requirements.external, 'external');
        validateKeys(requirements.external, VALID_EXTERNAL_TYPES);
        for (const type of VALID_EXTERNAL_TYPES) {
            if (type !== 'fetch' && type !== 'configurable') {
                validateArrayField(requirements.external[type], `external.${String(type)}`);
            }
        }
        if (requirements.external.fetch !== undefined) {
            validateObjectField(requirements.external.fetch, 'external.fetch');
            validateKeys(requirements.external.fetch, VALID_FETCH_TYPES);
            for (const type of VALID_FETCH_TYPES) {
                validateArrayField(requirements.external.fetch[type], `external.fetch.${String(type)}`);
            }
        }
    }
};
const getMissingFetchPermissions = (requiredFetch, currentlyGrantedFetch) => {
    if (!requiredFetch) {
        return undefined;
    }
    const missingFetch = {};
    Object.keys(requiredFetch).forEach((fetchType) => {
        const requiredUrls = requiredFetch[fetchType];
        if (!requiredUrls || !Array.isArray(requiredUrls) || requiredUrls.length === 0)
            return;
        const missingUrls = getMissingUrls(requiredUrls, currentlyGrantedFetch?.[fetchType] ?? [], fetchType === 'client');
        if (missingUrls.length) {
            missingFetch[fetchType] = missingUrls.map(extractUrlString);
        }
    });
    return Object.keys(missingFetch).length ? missingFetch : undefined;
};
const getMissingExternalPermissions = (requiredExternal, currentGrantedExternal) => {
    let missingExternal = undefined;
    Object.keys(requiredExternal).forEach((type) => {
        if (type === 'fetch') {
            const missingFetchPerms = getMissingFetchPermissions(requiredExternal.fetch, currentGrantedExternal.fetch);
            if (missingFetchPerms) {
                if (!missingExternal) {
                    missingExternal = {};
                }
                missingExternal.fetch = missingFetchPerms;
            }
            return;
        }
        if (type === 'configurable') {
            return;
        }
        const externalUrls = requiredExternal[type];
        if (!externalUrls || !Array.isArray(externalUrls) || externalUrls.length === 0) {
            return;
        }
        const missingUrls = getMissingUrls(externalUrls, currentGrantedExternal[type] || [], true);
        if (missingUrls.length > 0) {
            if (!missingExternal) {
                missingExternal = {};
            }
            missingExternal[type] = missingUrls.map(extractUrlString);
        }
    });
    return missingExternal;
};
const hasPermission = (requirements) => {
    return wrapInSyncMetrics({ name: 'api.permissions.hasPermission' }, () => hasPermissionWithoutMetrics(requirements));
};
exports.hasPermission = hasPermission;
const hasPermissionWithoutMetrics = (requirements) => {
    const appContext = (0, runtime_1.getAppContext)();
    const currentlyGrantedPermissions = appContext.permissions;
    const arePermissionsAvailable = !!(currentlyGrantedPermissions && typeof currentlyGrantedPermissions === 'object');
    if (!arePermissionsAvailable) {
        throw new errors_1.ApiNotReadyError('This feature is not available yet');
    }
    validatePermissionRequirements(requirements);
    const missingPermissions = {};
    let hasMissingPermissions = false;
    const missingScopes = getMissingScopes(requirements.scopes, currentlyGrantedPermissions.scopes);
    if (missingScopes) {
        missingPermissions.scopes = missingScopes;
        hasMissingPermissions = true;
    }
    if (requirements.external) {
        const { external: requiredExternal } = requirements;
        const currentlyGrantedExternal = currentlyGrantedPermissions.external || {};
        const missingExternalPerms = getMissingExternalPermissions(requiredExternal, currentlyGrantedExternal);
        if (missingExternalPerms) {
            missingPermissions.external = {
                ...missingPermissions.external,
                ...missingExternalPerms
            };
            hasMissingPermissions = true;
        }
    }
    return {
        granted: !hasMissingPermissions,
        ...(hasMissingPermissions && {
            missing: new runtime_1.MissingPermissions(missingPermissions.scopes, missingPermissions.external)
        })
    };
};
const hasScope = (scope) => {
    return wrapInSyncMetrics({ name: 'api.permissions.hasScope' }, () => hasPermissionWithoutMetrics({ scopes: [scope] }).granted);
};
exports.hasScope = hasScope;
const canFetchFrom = (type, url) => {
    return wrapInSyncMetrics({ name: 'api.permissions.canFetchFrom' }, () => hasPermissionWithoutMetrics({ external: { fetch: { [type]: [url] } } }).granted);
};
exports.canFetchFrom = canFetchFrom;
const canLoadResource = (type, url) => {
    return wrapInSyncMetrics({ name: 'api.permissions.canLoadResource' }, () => hasPermissionWithoutMetrics({ external: { [type]: [url] } }).granted);
};
exports.canLoadResource = canLoadResource;
exports.permissions = {
    hasPermission: exports.hasPermission,
    hasScope: exports.hasScope,
    canFetchFrom: exports.canFetchFrom,
    canLoadResource: exports.canLoadResource
};


/***/ },

/***/ 5429
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.MissingPermissions = exports.PermissionRequirements = exports.RuntimePermissions = exports.Permissions = void 0;
exports.__getRuntime = __getRuntime;
exports.getAppContext = getAppContext;
exports.wrapInMetrics = wrapInMetrics;
exports.bindInvocationContext = bindInvocationContext;
const errors_1 = __webpack_require__(9742);
const ari_1 = __webpack_require__(2167);
const extractUrlString = (item) => {
    if (typeof item === 'string') {
        return item;
    }
    else if ('address' in item) {
        return item.address;
    }
    else {
        return item.remote;
    }
};
const formatScopesSection = (scopes) => {
    if (scopes && Array.isArray(scopes) && scopes.length > 0) {
        return `Scopes: ${scopes.join(', ')}`;
    }
    return null;
};
const formatExternalSection = (external) => {
    if (!external) {
        return null;
    }
    const externalParts = [];
    Object.keys(external).forEach((type) => {
        if (type === 'fetch') {
            const fetchParts = getFetchPermissions(external.fetch);
            externalParts.push(...fetchParts);
        }
        else {
            const externalUrls = external[type];
            if (externalUrls && Array.isArray(externalUrls) && externalUrls.length > 0) {
                const capitalizedType = String(type).charAt(0).toUpperCase() + String(type).slice(1);
                const urlList = externalUrls.map(extractUrlString).join(', ');
                externalParts.push(`${capitalizedType}: ${urlList}`);
            }
        }
    });
    return externalParts.length > 0 ? `External: ${externalParts.join('; ')}` : null;
};
const getFetchPermissions = (fetch) => {
    if (!fetch) {
        return [];
    }
    const fetchParts = [];
    Object.keys(fetch).forEach((fetchType) => {
        const urls = fetch[fetchType];
        if (urls && urls.length > 0) {
            const urlList = urls.map(extractUrlString).join(', ');
            const capitalizedType = String(fetchType).charAt(0).toUpperCase() + String(fetchType).slice(1);
            fetchParts.push(`Fetch ${capitalizedType}: ${urlList}`);
        }
    });
    return fetchParts;
};
class Permissions {
    format() {
        const parts = [];
        const scopesSection = formatScopesSection(this.scopes);
        if (scopesSection) {
            parts.push(scopesSection);
        }
        const externalSection = formatExternalSection(this.external);
        if (externalSection) {
            parts.push(externalSection);
        }
        return parts.length > 0 ? parts.join('; ') : 'No permissions specified';
    }
}
exports.Permissions = Permissions;
class RuntimePermissions extends Permissions {
    scopes;
    external;
    constructor(scopes, external) {
        super();
        this.scopes = scopes;
        this.external = external;
    }
}
exports.RuntimePermissions = RuntimePermissions;
class PermissionRequirements extends Permissions {
    scopes;
    external;
    constructor(scopes, external) {
        super();
        this.scopes = scopes;
        this.external = external;
    }
}
exports.PermissionRequirements = PermissionRequirements;
class MissingPermissions extends Permissions {
    scopes;
    external;
    constructor(scopes, external) {
        super();
        this.scopes = scopes;
        this.external = external;
    }
}
exports.MissingPermissions = MissingPermissions;
function __getRuntime() {
    const runtime = global.__forge_runtime__;
    if (!runtime) {
        throw new Error('Forge runtime not found.');
    }
    return runtime;
}
function getAppContext() {
    const runtime = __getRuntime();
    const { appId, appVersion, environmentId, environmentType, invocationId, installationId, moduleKey, license, installation, remoteInstallationRegion, permissions } = runtime.appContext;
    const invocationRemainingTimeInMillis = runtime.lambdaContext.getRemainingTimeInMillis ??
        (() => {
            throw new Error('Lambda remaining time is not available. If tunnelling, update Forge CLI to the latest version.');
        });
    return {
        appAri: (0, ari_1.getAppAri)(appId),
        appVersion,
        environmentAri: (0, ari_1.getEnvironmentAri)(appId, environmentId),
        environmentType,
        installationAri: (0, ari_1.getInstallationAri)(installationId),
        invocationId,
        invocationRemainingTimeInMillis,
        moduleKey,
        license,
        installation,
        remoteInstallationRegion,
        permissions: new RuntimePermissions(permissions?.scopes || [], permissions?.external || {})
    };
}
function wrapInMetrics(name, fn) {
    return async (...args) => {
        const { metrics } = __getRuntime();
        metrics.counter(name).incr();
        const timer = metrics.timing(name).measure();
        let success = true;
        try {
            return await fn(...args);
        }
        catch (e) {
            const undiciError = global.__forge_undici_error__;
            if (e instanceof errors_1.ProxyRequestError ||
                (undiciError && typeof undiciError === 'function' && e instanceof undiciError)) {
                success = false;
            }
            throw e;
        }
        finally {
            timer.stop({ success: success.toString() });
        }
    };
}
function bindInvocationContext(fn) {
    const AsyncLocalStorage = (__webpack_require__(290).AsyncLocalStorage);
    return AsyncLocalStorage.bind(fn);
}


/***/ },

/***/ 9140
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";
var __webpack_unused_export__;

__webpack_unused_export__ = ({ value: true });
exports.authorize = void 0;
const auth_1 = __webpack_require__(3318);
const __1 = __webpack_require__(7274);
const authorize = () => {
    const accountId = (0, __1.__getRuntime)().aaid;
    if (!accountId) {
        throw new Error(`Couldn’t find the accountId of the invoking user. This API can only be used inside user-invoked modules.`);
    }
    return {
        ...(0, auth_1.authorizeConfluenceWithFetch)(async (path, opts) => {
            const res = await (0, __1.asUser)().requestConfluence((0, __1.assumeTrustedRoute)(path), opts);
            return res.json();
        }, accountId),
        ...(0, auth_1.authorizeJiraWithFetch)(async (path, opts) => {
            const res = await (0, __1.asUser)().requestJira((0, __1.assumeTrustedRoute)(path), opts);
            return res.json();
        }, accountId)
    };
};
exports.authorize = authorize;


/***/ },

/***/ 7274
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";
var __webpack_unused_export__;

__webpack_unused_export__ = ({ value: true });
__webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = exports.wE = exports.assumeTrustedRoute = __webpack_unused_export__ = __webpack_unused_export__ = exports.__getRuntime = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = exports.Tg = __webpack_unused_export__ = __webpack_unused_export__ = exports.asUser = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = __webpack_unused_export__ = void 0;
const endpoint_1 = __webpack_require__(972);
Object.defineProperty(exports, "Tg", ({ enumerable: true, get: function () { return endpoint_1.invokeRemote; } }));
__webpack_unused_export__ = ({ enumerable: true, get: function () { return endpoint_1.invokeService; } });
const fetch_1 = __webpack_require__(8265);
__webpack_unused_export__ = ({ enumerable: true, get: function () { return fetch_1.__fetchProduct; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return fetch_1.__requestAtlassianAsApp; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return fetch_1.__requestAtlassianAsUser; } });
const authorization_1 = __webpack_require__(9140);
__webpack_unused_export__ = ({ enumerable: true, get: function () { return authorization_1.authorize; } });
const privacy_1 = __webpack_require__(1317);
const webTrigger_1 = __webpack_require__(6014);
__webpack_unused_export__ = ({ enumerable: true, get: function () { return webTrigger_1.webTrigger; } });
const fetchAPI = (0, fetch_1.getFetchAPI)();
const asUser = fetchAPI.asUser;
exports.asUser = asUser;
const asApp = fetchAPI.asApp;
__webpack_unused_export__ = asApp;
const fetch = fetchAPI.fetch;
__webpack_unused_export__ = fetch;
const requestJira = fetchAPI.requestJira;
__webpack_unused_export__ = requestJira;
const requestConfluence = fetchAPI.requestConfluence;
__webpack_unused_export__ = requestConfluence;
const requestBitbucket = fetchAPI.requestBitbucket;
__webpack_unused_export__ = requestBitbucket;
const API = {
    ...fetchAPI,
    invokeRemote: endpoint_1.invokeRemote,
    invokeService: endpoint_1.invokeService
};
__webpack_unused_export__ = {
    reportPersonalData: (0, privacy_1.createReportPersonalData)(fetch_1.__requestAtlassianAsApp)
};
exports.Ay = API;
const createRequestStargateAsApp = () => fetch_1.__requestAtlassianAsApp;
__webpack_unused_export__ = createRequestStargateAsApp;
var errors_1 = __webpack_require__(9742);
__webpack_unused_export__ = ({ enumerable: true, get: function () { return errors_1.ExternalEndpointNotAllowedError; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return errors_1.FetchError; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return errors_1.FUNCTION_ERR; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return errors_1.HttpError; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return errors_1.InvalidWorkspaceRequestedError; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return errors_1.isExpectedError; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return errors_1.isForgePlatformError; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return errors_1.isHostedCodeError; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return errors_1.NeedsAuthenticationError; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return errors_1.NotAllowedError; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return errors_1.ProductEndpointNotAllowedError; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return errors_1.ProxyRequestError; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return errors_1.RequestProductNotAllowedError; } });
var runtime_1 = __webpack_require__(5429);
Object.defineProperty(exports, "__getRuntime", ({ enumerable: true, get: function () { return runtime_1.__getRuntime; } }));
__webpack_unused_export__ = ({ enumerable: true, get: function () { return runtime_1.bindInvocationContext; } });
__webpack_unused_export__ = ({ enumerable: true, get: function () { return runtime_1.getAppContext; } });
var safeUrl_1 = __webpack_require__(1228);
Object.defineProperty(exports, "assumeTrustedRoute", ({ enumerable: true, get: function () { return safeUrl_1.assumeTrustedRoute; } }));
Object.defineProperty(exports, "wE", ({ enumerable: true, get: function () { return safeUrl_1.route; } }));
__webpack_unused_export__ = ({ enumerable: true, get: function () { return safeUrl_1.routeFromAbsolute; } });
var i18n_1 = __webpack_require__(6613);
__webpack_unused_export__ = ({ enumerable: true, get: function () { return i18n_1.i18n; } });
var permissions_1 = __webpack_require__(3765);
__webpack_unused_export__ = ({ enumerable: true, get: function () { return permissions_1.permissions; } });


/***/ },

/***/ 1317
(__unused_webpack_module, exports) {

"use strict";
var __webpack_unused_export__;

__webpack_unused_export__ = ({ value: true });
exports.createReportPersonalData = exports.uK = exports.k = void 0;
exports.k = '/app/report-accounts';
exports.uK = 90;
const createReportPersonalData = (requestAtlassian) => {
    return function fetchUpdates(accounts) {
        if (accounts.length === 0) {
            return Promise.resolve([]);
        }
        const request = requestAtlassian(exports.k, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ accounts: accounts.slice(0, exports.uK) })
        }).then(async (resp) => {
            if (resp.status === 200) {
                return (await resp.json()).accounts;
            }
            if (resp.status === 204) {
                return [];
            }
            return Promise.reject(resp);
        });
        return Promise.all([request, fetchUpdates(accounts.slice(exports.uK))]).then(([first, second]) => first.concat(second));
    };
};
exports.createReportPersonalData = createReportPersonalData;


/***/ },

/***/ 1228
(__unused_webpack_module, exports) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.isRoute = isRoute;
exports.routeFromAbsolute = routeFromAbsolute;
exports.route = route;
exports.requireSafeUrl = requireSafeUrl;
exports.assumeTrustedRoute = assumeTrustedRoute;
class ReadonlyRoute {
    value_;
    constructor(value_) {
        this.value_ = value_;
    }
    set value(_) {
        throw new Error('modification of a Route is not allowed');
    }
    get value() {
        return this.value_;
    }
}
function isRoute(x) {
    return x instanceof ReadonlyRoute;
}
function routeFromAbsolute(absolutePath) {
    const absoluteURL = new URL(absolutePath);
    return assumeTrustedRoute(`${absoluteURL.pathname}${absoluteURL.search}`);
}
const DOUBLE_DOT = ['..', '.%2e', '%2e.', '%2e%2e', '.%2E', '%2E.', '%2E%2e'];
const DIRECTORY_PATH = ['/', '\\'];
const ENDS_PATH = ['?', '#'];
function containsOneOf(needles, haystack) {
    return needles.some((needle) => haystack.includes(needle));
}
function escapeParameter(parameter, mode) {
    switch (mode) {
        case 'path':
            if (isRoute(parameter)) {
                return parameter.value;
            }
            parameter = String(parameter);
            if (containsOneOf(DOUBLE_DOT, parameter) ||
                containsOneOf(ENDS_PATH, parameter) ||
                containsOneOf(DIRECTORY_PATH, parameter)) {
                throw new Error('Disallowing path manipulation attempt. For more information see: https://go.atlassian.com/product-fetch-api-route');
            }
            return parameter;
        case 'query':
            if (isRoute(parameter)) {
                return encodeURIComponent(parameter.value);
            }
            else if (parameter instanceof URLSearchParams) {
                return parameter.toString();
            }
            else {
                return encodeURIComponent(parameter);
            }
    }
}
function route(template, ...parameters) {
    let mode = 'path';
    let result = '';
    for (let i = 0; i < template.length; i++) {
        const templateFragment = template[i];
        if (containsOneOf(ENDS_PATH, templateFragment)) {
            mode = 'query';
        }
        result += templateFragment;
        if (i >= parameters.length) {
            break;
        }
        result += escapeParameter(parameters[i], mode);
    }
    return new ReadonlyRoute(result);
}
function requireSafeUrl(url) {
    if (url instanceof ReadonlyRoute) {
        return url;
    }
    throw new Error(`You must create your route using the 'route' export from '@forge/api'.
See https://go.atlassian.com/forge-fetch-route for more information.`);
}
function assumeTrustedRoute(route) {
    return new ReadonlyRoute(route);
}


/***/ },

/***/ 6014
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";
var __webpack_unused_export__;

__webpack_unused_export__ = ({ value: true });
exports.webTrigger = void 0;
const runtime_1 = __webpack_require__(5429);
const fetch_1 = __webpack_require__(8265);
const proxyGetWebTriggerURL = (0, runtime_1.wrapInMetrics)('api.getWebTriggerUrl', async (webTriggerModuleKey, forceCreate, secretKeyConfig) => {
    const runtime = (0, runtime_1.__getRuntime)();
    const input = {
        appId: runtime.appContext.appId,
        envId: runtime.appContext.environmentId,
        triggerKey: webTriggerModuleKey,
        contextId: runtime.contextAri,
        ...(secretKeyConfig !== undefined
            ? {
                secretKeyConfig: {
                    key: secretKeyConfig.key,
                    ...(secretKeyConfig.noExpiry !== undefined ? { noExpiry: secretKeyConfig.noExpiry } : {})
                }
            }
            : {})
    };
    const response = await (0, fetch_1.__requestAtlassianAsApp)('/graphql', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query: `
            mutation forge_app_createWebTriggerUrl($input: WebTriggerUrlInput!, $forceCreate: Boolean) {
              createWebTriggerUrl(input: $input, forceCreate: $forceCreate) {
                url
              }
            }
          `,
            variables: {
                input,
                forceCreate
            }
        })
    });
    if (!response.ok) {
        throw new Error(`Internal error occurred: Failed to get web trigger URL: ${response.statusText}.`);
    }
    const responseBody = (await response.json());
    if (!responseBody?.data?.createWebTriggerUrl?.url) {
        throw new Error(`Internal error occurred: Failed to get web trigger URL.`);
    }
    return responseBody.data.createWebTriggerUrl.url;
});
const proxyDeleteWebTriggerURL = (0, runtime_1.wrapInMetrics)('api.deleteWebTriggerUrl', async (webTriggerUrl) => {
    const webTriggerUrlIdRegexGroupMatch = /\/(?:x1|public)\/([^\/\?\#]+)/;
    const matches = webTriggerUrl.match(webTriggerUrlIdRegexGroupMatch);
    if (!matches || matches.length < 2) {
        throw new Error('Internal error occurred: Failed to parse web trigger URL for ID');
    }
    const id = matches[1];
    const runtime = (0, runtime_1.__getRuntime)();
    const response = await (0, fetch_1.__requestAtlassianAsApp)('/graphql', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query: `
            mutation forge_app_deleteWebTriggerUrl($id: ID!, $installationId: ID) {
              deleteWebTriggerUrl(id: $id, installationId: $installationId) {
                success
                message
              }
            }
          `,
            variables: {
                id,
                installationId: runtime.appContext.installationId
            }
        })
    });
    if (!response.ok) {
        throw new Error(`Internal error occurred: Failed to delete web trigger URL: ${response.statusText}.`);
    }
    const responseBody = (await response.json());
    if (!responseBody?.data?.deleteWebTriggerUrl?.success) {
        const errorText = responseBody?.data?.deleteWebTriggerUrl?.message || 'unknown error';
        throw new Error(`Internal error occurred: Failed to delete web trigger URL: ${errorText}`);
    }
});
const proxyQueryWebTriggerURLs = (0, runtime_1.wrapInMetrics)('api.queryWebTriggerUrls', async (moduleKey) => {
    const runtime = (0, runtime_1.__getRuntime)();
    const response = await (0, fetch_1.__requestAtlassianAsApp)('/graphql', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query: `
            query forge_app_webTriggerUrlsByAppContext($appId: ID!, $envId: ID!, $contextId: ID!) {
              webTriggerUrlsByAppContext(appId: $appId, envId: $envId, contextId: $contextId) {
                triggerKey
                url
              }
            }
          `,
            variables: {
                appId: runtime.appContext.appId,
                envId: runtime.appContext.environmentId,
                contextId: runtime.contextAri
            }
        })
    });
    if (!response.ok) {
        throw new Error(`Internal error occurred: Failed to get web trigger URLs: ${response.statusText}.`);
    }
    const responseBody = (await response.json());
    if (!responseBody?.data?.webTriggerUrlsByAppContext) {
        throw new Error('Internal error occurred: No data from web trigger URLs query.');
    }
    let result = responseBody.data.webTriggerUrlsByAppContext;
    if (moduleKey) {
        result = result.filter((webTriggerResult) => webTriggerResult.triggerKey === moduleKey);
    }
    result = result.map((webTriggerResult) => ({
        moduleKey: webTriggerResult.triggerKey,
        url: webTriggerResult.url
    }));
    return result;
});
exports.webTrigger = {
    getUrl: async (webTriggerModuleKey, optionsOrForceCreate) => {
        const forceCreate = typeof optionsOrForceCreate === 'boolean' ? optionsOrForceCreate : optionsOrForceCreate?.forceCreate ?? false;
        const secretKeyConfig = typeof optionsOrForceCreate === 'object' && optionsOrForceCreate !== null
            ? optionsOrForceCreate.secretKeyConfig
            : undefined;
        return proxyGetWebTriggerURL(webTriggerModuleKey, forceCreate, secretKeyConfig);
    },
    deleteUrl: async (webTriggerUrl) => proxyDeleteWebTriggerURL(webTriggerUrl),
    queryUrls: async (moduleKey) => proxyQueryWebTriggerURLs(moduleKey)
};


/***/ },

/***/ 3534
(__unused_webpack_module, exports) {

"use strict";
var __webpack_unused_export__;

__webpack_unused_export__ = ({ value: true });
exports.createApiMethods = void 0;
const fromEntries = (array) => {
    return array.reduce((acc, [key, value]) => {
        acc[key] = value;
        return acc;
    }, {});
};
const createApiMethods = (methodToPermissionMap, permissionCheckFactory) => {
    const apiMethodEntries = Object.entries(methodToPermissionMap).map(([methodName, permission]) => [methodName, permissionCheckFactory(permission)]);
    return fromEntries(apiMethodEntries);
};
exports.createApiMethods = createApiMethods;


/***/ },

/***/ 3445
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.authorizeConfluenceWithFetch = void 0;
const tslib_1 = __webpack_require__(1635);
const api_1 = __webpack_require__(3534);
const permissions_1 = tslib_1.__importDefault(__webpack_require__(8393));
const checkConfluencePermissions = async (requestConfluence, accountId, contentId, permission) => {
    const res = await requestConfluence(`/rest/api/content/${contentId}/permission/check`, {
        method: 'post',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
            subject: {
                type: 'user',
                identifier: accountId
            },
            operation: permission
        })
    });
    return res;
};
const getPermissionsCheckFactory = (requestConfluence, accountId, contentId) => (permission) => {
    return async () => {
        const res = await checkConfluencePermissions(requestConfluence, accountId, contentId, permission);
        return Boolean(res?.hasPermission);
    };
};
const authorizeConfluenceWithFetch = (requestConfluence, accountId) => {
    return {
        onConfluenceContent: (contentId) => (0, api_1.createApiMethods)(permissions_1.default, getPermissionsCheckFactory(requestConfluence, accountId, contentId))
    };
};
exports.authorizeConfluenceWithFetch = authorizeConfluenceWithFetch;


/***/ },

/***/ 8393
(__unused_webpack_module, exports) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
const API_PERMISSIONS_MAP = {
    canRead: 'read',
    canUpdate: 'update',
    canDelete: 'delete'
};
exports["default"] = API_PERMISSIONS_MAP;


/***/ },

/***/ 3318
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";
var __webpack_unused_export__;

__webpack_unused_export__ = ({ value: true });
exports.authorizeJiraWithFetch = exports.authorizeConfluenceWithFetch = void 0;
var confluence_1 = __webpack_require__(3445);
Object.defineProperty(exports, "authorizeConfluenceWithFetch", ({ enumerable: true, get: function () { return confluence_1.authorizeConfluenceWithFetch; } }));
var jira_1 = __webpack_require__(3743);
Object.defineProperty(exports, "authorizeJiraWithFetch", ({ enumerable: true, get: function () { return jira_1.authorizeJiraWithFetch; } }));


/***/ },

/***/ 3743
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.authorizeJiraWithFetch = void 0;
const api_1 = __webpack_require__(3534);
const permissions_1 = __webpack_require__(8207);
const arrayEquals = (a, b) => {
    return JSON.stringify(Array.from(a.map(String)).sort()) === JSON.stringify(Array.from(b.map(String)).sort());
};
const checkJiraPermissions = async (requestJira, accountId, projectPermissions) => {
    const res = await requestJira('/rest/api/3/permissions/check', {
        method: 'post',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
            accountId,
            projectPermissions
        })
    });
    return res;
};
const hasPermissionsForEntities = (projectPermissions, permission, type, entities) => {
    if (!entities || entities.length === 0)
        return true;
    const allowedEntities = projectPermissions.find((permissionResponse) => permissionResponse.permission === permission)?.[type];
    return !!allowedEntities && arrayEquals(allowedEntities, entities);
};
const getPermissionCheckFactory = (requestJira, accountId, type, entities) => (permission) => {
    return async () => {
        const { projectPermissions } = await checkJiraPermissions(requestJira, accountId, [
            {
                permissions: [permission],
                [type]: entities
            }
        ]);
        return hasPermissionsForEntities(projectPermissions, permission, type, entities);
    };
};
const toArray = (id) => (Array.isArray(id) ? id : [id]);
const authorizeJiraWithFetch = (requestJira, accountId) => {
    return {
        onJira: async (projectPermissionsInput) => {
            const result = await checkJiraPermissions(requestJira, accountId, projectPermissionsInput);
            return result.projectPermissions || [];
        },
        onJiraProject: (projects) => (0, api_1.createApiMethods)(permissions_1.API_PROJECTS_PERMISSIONS_MAP, getPermissionCheckFactory(requestJira, accountId, 'projects', toArray(projects))),
        onJiraIssue: (issues) => (0, api_1.createApiMethods)(permissions_1.API_ISSUES_PERMISSIONS_MAP, getPermissionCheckFactory(requestJira, accountId, 'issues', toArray(issues)))
    };
};
exports.authorizeJiraWithFetch = authorizeJiraWithFetch;


/***/ },

/***/ 8207
(__unused_webpack_module, exports) {

"use strict";
var __webpack_unused_export__;

__webpack_unused_export__ = ({ value: true });
exports.API_PROJECTS_PERMISSIONS_MAP = exports.API_ISSUES_PERMISSIONS_MAP = void 0;
const API_ISSUES_PERMISSIONS_MAP = {
    canAssign: 'ASSIGN_ISSUES',
    canCreate: 'CREATE_ISSUES',
    canEdit: 'EDIT_ISSUES',
    canMove: 'MOVE_ISSUES',
    canDelete: 'DELETE_ISSUES',
    canAddComments: 'ADD_COMMENTS',
    canEditAllComments: 'EDIT_ALL_COMMENTS',
    canDeleteAllComments: 'DELETE_ALL_COMMENTS',
    canCreateAttachments: 'CREATE_ATTACHMENTS',
    canDeleteAllAttachments: 'DELETE_ALL_ATTACHMENTS'
};
exports.API_ISSUES_PERMISSIONS_MAP = API_ISSUES_PERMISSIONS_MAP;
const API_PROJECTS_PERMISSIONS_MAP = {
    canAssignIssues: 'ASSIGN_ISSUES',
    canCreateIssues: 'CREATE_ISSUES',
    canEditIssues: 'EDIT_ISSUES',
    canMoveIssues: 'MOVE_ISSUES',
    canDeleteIssues: 'DELETE_ISSUES',
    canAddComments: 'ADD_COMMENTS',
    canEditAllComments: 'EDIT_ALL_COMMENTS',
    canDeleteAllComments: 'DELETE_ALL_COMMENTS',
    canCreateAttachments: 'CREATE_ATTACHMENTS',
    canDeleteAllAttachments: 'DELETE_ALL_ATTACHMENTS'
};
exports.API_PROJECTS_PERMISSIONS_MAP = API_PROJECTS_PERMISSIONS_MAP;


/***/ },

/***/ 7953
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.EgressFilteringService = void 0;
const url_parser_1 = __webpack_require__(6836);
const utils_1 = __webpack_require__(7194);
class EgressFilteringService {
    constructor(allowList) {
        this.URLs = allowList.filter((domainOrURL) => !domainOrURL.startsWith('*')).map((url) => this.parseUrl(url));
        this.wildcardDomains = allowList
            .filter((domainOrURL) => domainOrURL !== '*')
            .map((url) => this.parseUrl(url))
            .filter((url) => decodeURIComponent(url.hostname).startsWith('*'))
            .map((url) => ({
            ...url,
            regex: (0, utils_1.globToRegex)(decodeURIComponent(url.hostname))
        }));
        this.allowsEverything = allowList.includes('*');
    }
    parseUrl(url) {
        return (0, url_parser_1.parseUrl)(url);
    }
    containsWildCardEgress() {
        return this.allowsEverything;
    }
    isValidUrl(url) {
        if (this.allowsEverything) {
            return true;
        }
        const parsedUrl = this.parseUrl(url);
        return this.allowedDomainExact(parsedUrl, this.URLs) || this.allowedDomainPattern(parsedUrl, this.wildcardDomains);
    }
    isValidUrlCSP(url) {
        if (this.allowsEverything) {
            return true;
        }
        const parsedUrl = this.parseUrl(url);
        return (this.allowedDomainExactAndPath(parsedUrl, this.URLs) ||
            this.allowedDomainPatternAndPath(parsedUrl, this.wildcardDomains));
    }
    allowedDomainExact(domain, allowList) {
        return allowList
            .filter((allowed) => allowed.protocol === domain.protocol)
            .some((url) => url.hostname === domain.hostname);
    }
    allowedDomainExactAndPath(domain, allowList) {
        return allowList
            .filter((allowed) => this.protocolMatchesCSP(allowed.protocol, domain.protocol))
            .filter((allowed) => allowed.hostname === domain.hostname)
            .some((allowed) => this.pathMatches(allowed.pathname, domain.pathname));
    }
    allowedDomainPattern(domain, allowList) {
        return allowList
            .filter((allowed) => allowed.protocol === domain.protocol)
            .some((pattern) => pattern.regex.test(domain.hostname));
    }
    allowedDomainPatternAndPath(domain, allowList) {
        return allowList
            .filter((pattern) => this.protocolMatchesCSP(pattern.protocol, domain.protocol))
            .filter((pattern) => pattern.regex.test(domain.hostname))
            .some((allowed) => this.pathMatches(allowed.pathname, domain.pathname));
    }
    protocolMatchesCSP(allowedProtocol, requestProtocol) {
        if (allowedProtocol === requestProtocol) {
            return true;
        }
        if (allowedProtocol === 'http:' && requestProtocol === 'https:') {
            return true;
        }
        if (allowedProtocol === 'ws:' && requestProtocol === 'wss:') {
            return true;
        }
        return false;
    }
    pathMatches(allowedPath, requestPath) {
        if (allowedPath === '/') {
            return true;
        }
        if (allowedPath.endsWith('/')) {
            return requestPath.startsWith(allowedPath);
        }
        return requestPath === allowedPath;
    }
}
exports.EgressFilteringService = EgressFilteringService;


/***/ },

/***/ 1839
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
const tslib_1 = __webpack_require__(1635);
tslib_1.__exportStar(__webpack_require__(7953), exports);
tslib_1.__exportStar(__webpack_require__(6836), exports);
tslib_1.__exportStar(__webpack_require__(7194), exports);


/***/ },

/***/ 6836
(__unused_webpack_module, exports) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.parseUrl = parseUrl;
function parseUrl(url) {
    var _a, _b;
    const protocol = (_b = (_a = url.match(/^(.*?:)/)) === null || _a === void 0 ? void 0 : _a[0]) !== null && _b !== void 0 ? _b : 'https:';
    const hostAndPath = url.replace(protocol, '').replace(/^\/*/, '').replace(/^\\*/, '').split('?')[0].split('#')[0];
    const hostname = hostAndPath.split('/')[0];
    const pathname = hostAndPath.slice(hostname.length) || '/';
    return { protocol, hostname, pathname };
}


/***/ },

/***/ 7194
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.getEgressesBasedOnToggles = exports.sortAndGroupEgressPermissionsByDomain = exports.EgressCategory = exports.EgressType = void 0;
exports.globToRegex = globToRegex;
const url_parser_1 = __webpack_require__(6836);
function globToRegex(pattern) {
    const escaped = pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&');
    const regexPattern = escaped.replace(/\*/g, '.*');
    return new RegExp(`^${regexPattern}$`);
}
const sortAndGroupEgressPermissionsByDomain = (egressAddresses) => {
    if ((egressAddresses === null || egressAddresses === void 0 ? void 0 : egressAddresses.length) === 0) {
        return [];
    }
    const protocolRegex = /^(.*?:\/\/)/;
    const domains = new Set();
    const wildcardDomains = [];
    egressAddresses.forEach((item) => {
        const itemWithProtocol = protocolRegex.test(item) ? item : `https://${item}`;
        const url = (0, url_parser_1.parseUrl)(itemWithProtocol);
        if (url.hostname.startsWith('*')) {
            domains.add(url.hostname.substring(2));
            wildcardDomains.push(globToRegex(url.hostname));
        }
        else {
            domains.add(url.hostname);
        }
    });
    return [...domains].sort().reduce((grouped, domain) => {
        if (!wildcardDomains.some((pattern) => pattern.test(domain))) {
            grouped.push(domain);
        }
        return grouped;
    }, []);
};
exports.sortAndGroupEgressPermissionsByDomain = sortAndGroupEgressPermissionsByDomain;
var EgressType;
(function (EgressType) {
    EgressType["FetchBackendSide"] = "FETCH_BACKEND_SIDE";
    EgressType["FetchClientSide"] = "FETCH_CLIENT_SIDE";
    EgressType["Fonts"] = "FONTS";
    EgressType["Frames"] = "FRAMES";
    EgressType["Images"] = "IMAGES";
    EgressType["Media"] = "MEDIA";
    EgressType["Scripts"] = "SCRIPTS";
    EgressType["Styles"] = "STYLES";
})(EgressType || (exports.EgressType = EgressType = {}));
var EgressCategory;
(function (EgressCategory) {
    EgressCategory["ANALYTICS"] = "ANALYTICS";
})(EgressCategory || (exports.EgressCategory = EgressCategory = {}));
const getEgressesBasedOnToggles = (input) => {
    const filteredEgresses = input.egress.filter((egress) => {
        var _a;
        if (((_a = egress.category) === null || _a === void 0 ? void 0 : _a.toUpperCase()) === EgressCategory.ANALYTICS) {
            if (input.installationConfig) {
                const analyticsConfig = input.installationConfig.find((config) => config.key.toUpperCase() === 'ALLOW_EGRESS_ANALYTICS');
                return (analyticsConfig === null || analyticsConfig === void 0 ? void 0 : analyticsConfig.value) !== false;
            }
            else {
                return input.overrides.ALLOW_EGRESS_ANALYTICS !== false;
            }
        }
        return true;
    });
    const egressByType = new Map();
    for (const egress of filteredEgresses) {
        if (!egressByType.has(egress.type)) {
            egressByType.set(egress.type, egress.addresses);
        }
        egressByType.set(egress.type, [...egressByType.get(egress.type), ...egress.addresses]);
    }
    return [...egressByType.entries()].map(([type, egresses]) => ({
        type,
        addresses: [...new Set(egresses)]
    }));
};
exports.getEgressesBasedOnToggles = getEgressesBasedOnToggles;


/***/ },

/***/ 6079
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
const tslib_1 = __webpack_require__(1635);
tslib_1.__exportStar(__webpack_require__(1839), exports);


/***/ },

/***/ 6893
(__unused_webpack_module, exports) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.FORGE_SUPPORTED_LOCALE_CODES = exports.I18N_BUNDLE_FOLDER_NAME = exports.I18N_INFO_FILE_NAME = void 0;
exports.I18N_INFO_FILE_NAME = 'i18n-info.json';
exports.I18N_BUNDLE_FOLDER_NAME = '__LOCALES__';
exports.FORGE_SUPPORTED_LOCALE_CODES = [
    'zh-CN',
    'zh-TW',
    'cs-CZ',
    'da-DK',
    'nl-NL',
    'en-US',
    'en-GB',
    'et-EE',
    'fi-FI',
    'fr-FR',
    'de-DE',
    'hu-HU',
    'is-IS',
    'it-IT',
    'ja-JP',
    'ko-KR',
    'no-NO',
    'pl-PL',
    'pt-BR',
    'pt-PT',
    'ro-RO',
    'ru-RU',
    'sk-SK',
    'tr-TR',
    'es-ES',
    'sv-SE'
];


/***/ },

/***/ 7898
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.ensureLocale = void 0;
const constants_1 = __webpack_require__(6893);
const forgeSupportedLocaleCodesSet = new Set(constants_1.FORGE_SUPPORTED_LOCALE_CODES);
const localeFallbacks = {
    'en-UK': 'en-GB',
    'nb-NO': 'no-NO'
};
const languageToLocaleCodeMap = constants_1.FORGE_SUPPORTED_LOCALE_CODES.reduce((agg, code) => {
    const [lng] = code.split('-');
    if (!agg[lng]) {
        agg[lng] = code;
    }
    return agg;
}, {
    nb: 'no-NO',
    pt: 'pt-PT'
});
const ensureLocale = (rawLocale) => {
    const locale = rawLocale.replace('_', '-');
    if (forgeSupportedLocaleCodesSet.has(locale)) {
        return locale;
    }
    return languageToLocaleCodeMap[locale] ?? localeFallbacks[locale] ?? null;
};
exports.ensureLocale = ensureLocale;


/***/ },

/***/ 4280
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.getI18nSupportedModuleEntries = exports.extractI18nPropertiesFromModules = exports.extractI18nKeysFromModules = exports.getTranslationValue = void 0;
const tslib_1 = __webpack_require__(1635);
tslib_1.__exportStar(__webpack_require__(6893), exports);
tslib_1.__exportStar(__webpack_require__(6829), exports);
tslib_1.__exportStar(__webpack_require__(1100), exports);
tslib_1.__exportStar(__webpack_require__(7898), exports);
var translationValueGetter_1 = __webpack_require__(1813);
Object.defineProperty(exports, "getTranslationValue", ({ enumerable: true, get: function () { return translationValueGetter_1.getTranslationValue; } }));
var moduleI18nHelper_1 = __webpack_require__(9962);
Object.defineProperty(exports, "extractI18nKeysFromModules", ({ enumerable: true, get: function () { return moduleI18nHelper_1.extractI18nKeysFromModules; } }));
Object.defineProperty(exports, "extractI18nPropertiesFromModules", ({ enumerable: true, get: function () { return moduleI18nHelper_1.extractI18nPropertiesFromModules; } }));
Object.defineProperty(exports, "getI18nSupportedModuleEntries", ({ enumerable: true, get: function () { return moduleI18nHelper_1.getI18nSupportedModuleEntries; } }));
tslib_1.__exportStar(__webpack_require__(5181), exports);


/***/ },

/***/ 9962
(__unused_webpack_module, exports) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.extractI18nPropertiesFromModules = exports.extractI18nKeysFromModules = exports.getI18nSupportedModuleEntries = void 0;
const isObject = (value) => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};
const isI18nValue = (value) => {
    return typeof value?.i18n === 'string';
};
const isConnectModuleKey = (moduleKey) => moduleKey.startsWith('connect-');
const isCoreModuleKey = (moduleKey) => moduleKey.startsWith('core:');
const getI18nKeysFromObject = (obj) => {
    const visited = new Set();
    const visit = (value, i18nPath) => {
        if (!isObject(value) || visited.has(value)) {
            return [];
        }
        visited.add(value);
        return Object.entries(value).flatMap(([propKey, propValue]) => {
            const currentPath = [...i18nPath, propKey];
            if (isI18nValue(propValue)) {
                return [{ propertyPath: currentPath, key: propValue.i18n }];
            }
            else if (Array.isArray(propValue)) {
                return propValue.flatMap((item) => visit(item, currentPath));
            }
            return visit(propValue, currentPath);
        });
    };
    return visit(obj, []);
};
const getI18nSupportedModuleEntries = (modules) => {
    return Object.entries(modules).flatMap(([moduleKey, moduleEntries]) => {
        if (!isConnectModuleKey(moduleKey) &&
            !isCoreModuleKey(moduleKey) &&
            moduleEntries &&
            Array.isArray(moduleEntries) &&
            moduleEntries.length > 0) {
            return moduleEntries.map((moduleEntry) => [moduleEntry, moduleKey]);
        }
        return [];
    });
};
exports.getI18nSupportedModuleEntries = getI18nSupportedModuleEntries;
const extractI18nKeysFromModules = (modules) => {
    const i18nKeys = new Set();
    for (const moduleEntry of (0, exports.getI18nSupportedModuleEntries)(modules)) {
        const i18nKeysForEntryValue = getI18nKeysFromObject(moduleEntry[0]);
        for (const { key } of i18nKeysForEntryValue) {
            i18nKeys.add(key);
        }
    }
    return i18nKeys.size > 0 ? Array.from(i18nKeys) : [];
};
exports.extractI18nKeysFromModules = extractI18nKeysFromModules;
const extractI18nPropertiesFromModules = (modules) => {
    const moduleI18nProperties = [];
    for (const moduleEntry of (0, exports.getI18nSupportedModuleEntries)(modules)) {
        const i18nKeysForEntryValue = getI18nKeysFromObject(moduleEntry[0]);
        for (const i18nObj of i18nKeysForEntryValue) {
            moduleI18nProperties.push({ moduleName: moduleEntry[1], ...i18nObj });
        }
    }
    return moduleI18nProperties;
};
exports.extractI18nPropertiesFromModules = extractI18nPropertiesFromModules;


/***/ },

/***/ 1813
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.getTranslationValueFromContent = exports.getTranslationValue = void 0;
const tslib_1 = __webpack_require__(1635);
const get_1 = tslib_1.__importDefault(__webpack_require__(8156));
const getTranslationValue = (translationLookup, i18nKey, locale) => {
    const translation = translationLookup[locale];
    if (!translation) {
        return null;
    }
    return (0, exports.getTranslationValueFromContent)(translation, i18nKey);
};
exports.getTranslationValue = getTranslationValue;
const getTranslationValueFromContent = (translationContent, i18nKey) => {
    let translationValue = translationContent[i18nKey];
    if (!translationValue) {
        const keyTokens = i18nKey.split('.');
        if (keyTokens.length > 1) {
            translationValue = (0, get_1.default)(translationContent, keyTokens, null);
        }
    }
    return typeof translationValue === 'string' ? translationValue : null;
};
exports.getTranslationValueFromContent = getTranslationValueFromContent;


/***/ },

/***/ 6829
(__unused_webpack_module, exports) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.TranslationsGetter = exports.TranslationGetterError = void 0;
const pushIfNotExists = (array, item) => {
    if (!array.includes(item)) {
        array.push(item);
    }
};
class TranslationGetterError extends Error {
    constructor(message) {
        super(message);
        this.name = 'TranslationGetterError';
    }
}
exports.TranslationGetterError = TranslationGetterError;
class TranslationsGetter {
    resourcesAccessor;
    i18nInfoConfig = null;
    translationResources = new Map();
    constructor(resourcesAccessor) {
        this.resourcesAccessor = resourcesAccessor;
    }
    async getTranslations(locale, options = { fallback: true }) {
        const i18nInfoConfig = await this.getI18nInfoConfig();
        const { fallback } = options;
        if (!fallback) {
            let translationResource;
            if (i18nInfoConfig.locales.includes(locale)) {
                translationResource = await this.getTranslationResource(locale);
            }
            return {
                translations: translationResource ?? null,
                locale
            };
        }
        for (const targetLocale of this.getLocaleLookupOrder(locale, i18nInfoConfig)) {
            const translationResource = await this.getTranslationResource(targetLocale);
            if (translationResource) {
                return {
                    translations: translationResource,
                    locale: targetLocale
                };
            }
        }
        return {
            translations: null,
            locale
        };
    }
    async getTranslationsByLocaleLookupOrder(locale) {
        const i18nInfoConfig = await this.getI18nInfoConfig();
        const lookupOrder = this.getLocaleLookupOrder(locale, i18nInfoConfig);
        return await Promise.all(lookupOrder.map(async (targetLocale) => {
            const translationResource = await this.getTranslationResource(targetLocale);
            return {
                locale: targetLocale,
                translations: translationResource
            };
        }));
    }
    reset() {
        this.i18nInfoConfig = null;
        this.translationResources.clear();
    }
    async getTranslationResource(locale) {
        let resource = this.translationResources.get(locale);
        if (!resource) {
            try {
                resource = await this.resourcesAccessor.getTranslationResource(locale);
                this.translationResources.set(locale, resource);
            }
            catch (error) {
                if (error instanceof TranslationGetterError) {
                    throw error;
                }
                throw new TranslationGetterError(`Failed to get translation resource for locale: ${locale}`);
            }
        }
        return resource;
    }
    async getI18nInfoConfig() {
        if (!this.i18nInfoConfig) {
            try {
                this.i18nInfoConfig = await this.resourcesAccessor.getI18nInfoConfig();
            }
            catch (error) {
                if (error instanceof TranslationGetterError) {
                    throw error;
                }
                throw new TranslationGetterError('Failed to get i18n info config');
            }
        }
        return this.i18nInfoConfig;
    }
    getLocaleLookupOrder(locale, config) {
        const { locales, fallback } = config;
        const lookupOrder = [locale];
        const fallbackLocales = fallback[locale];
        if (fallbackLocales && Array.isArray(fallbackLocales) && fallbackLocales.length > 0) {
            lookupOrder.push(...fallbackLocales);
        }
        pushIfNotExists(lookupOrder, config.fallback.default);
        return lookupOrder.filter((locale) => locales.includes(locale));
    }
}
exports.TranslationsGetter = TranslationsGetter;


/***/ },

/***/ 1100
(__unused_webpack_module, exports, __webpack_require__) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.Translator = void 0;
const translationValueGetter_1 = __webpack_require__(1813);
class Translator {
    locale;
    translationsGetter;
    localeLookupOrderedTranslations = null;
    cache = new Map();
    constructor(locale, translationsGetter) {
        this.locale = locale;
        this.translationsGetter = translationsGetter;
    }
    async init() {
        this.localeLookupOrderedTranslations = await this.translationsGetter.getTranslationsByLocaleLookupOrder(this.locale);
    }
    translate(i18nKey) {
        if (!this.localeLookupOrderedTranslations) {
            throw new Error('TranslationLookup not initialized');
        }
        let result = this.cache.get(i18nKey);
        if (result === undefined) {
            for (const { translations } of this.localeLookupOrderedTranslations) {
                const translationValue = (0, translationValueGetter_1.getTranslationValueFromContent)(translations, i18nKey);
                if (translationValue !== null) {
                    result = translationValue;
                    break;
                }
            }
            result = result ?? null;
            this.cache.set(i18nKey, result);
        }
        return result;
    }
}
exports.Translator = Translator;


/***/ },

/***/ 5181
(__unused_webpack_module, exports) {

"use strict";

Object.defineProperty(exports, "__esModule", ({ value: true }));


/***/ },

/***/ 3752
(module) {

(()=>{"use strict";const e={d:(r,t)=>{if(Array.isArray(t))for(var s=0;s<t.length;){var o=t[s++],i=t[s++];e.o(r,o)?0===i&&s++:0===i?Object.defineProperty(r,o,{enumerable:!0,value:t[s++]}):Object.defineProperty(r,o,{enumerable:!0,get:i})}else for(var o in t)e.o(t,o)&&!e.o(r,o)&&Object.defineProperty(r,o,{enumerable:!0,get:t[o]})},o:(e,r)=>Object.prototype.hasOwnProperty.call(e,r),r:e=>{Symbol.toStringTag&&Object.defineProperty(e,Symbol.toStringTag,{value:"Module"}),Object.defineProperty(e,"__esModule",{value:!0})}};let r={};e.r(r),e.d(r,{AnyAri:()=>p,Ari:()=>d,CompassWorkspaceAri:()=>m,ConfluenceWorkspaceAri:()=>w,EcosystemAppAri:()=>v,EcosystemAppEnvironmentVersionAri:()=>S,EcosystemAppPlacementAri:()=>T,GraphWorkspaceAri:()=>$,JiraWorkspaceAri:()=>k});var t=class extends Error{};function s(e){if("cloud"!==e&&"third-party"!==e)throw new t(`Identifier must have a qualifier of 'cloud' or 'third-party'. Received: ${e}`)}function o(e){if("ati"!==e)throw new t(`ATI must have a qualifier of 'ati'. Received: ${e}`)}var i=class{static getIdentifierSegments(e,r){let s=e.split(":");if(s.length<r)throw new t(`Input string must have ${r} segments.`);return s.length>r?[...s.slice(0,4),s.slice(4,s.length).join(":")]:s}};function a(e,r){if(r&&e!==r)throw new t(`Invalid resource owner - ${e}, expected ${r}.`)}function u(e,r){if(r&&e!==r)throw new t(`Invalid resource type - ${e}, expected ${r}.`)}var n=class extends i{static fromString(e,r){let t=this.getIdentifierSegments(e,5),[s,o,i,a,u]=t,[n,...c]=u.split("/"),l={qualifier:s,platformQualifier:o,cloudId:a,resourceOwner:i,resourceType:n,resourceId:c.join("/"),resourceIdSegmentValues:null!=r&&r.resourceIdSlug?this.ariSegmentValuesFromSlug(r.resourceIdSlug,c.join("/"),Object.keys(r.resourceIdSegmentFormats)):{}};return this.fromOpts(l,r)}static fromOpts(e,r){let{qualifier:o="ari",platformQualifier:i="cloud",resourceOwner:n,cloudId:c,resourceId:l,resourceIdSegmentValues:d,resourceType:p}=e;return function(e){if("ari"!==e)throw new t(`ARI must have a qualifier of 'ari'. Received: ${e}`)}(o),s(i),function(e,r=new RegExp("^[a-zA-Z0-9_\\-.]{0,255}$")){if(!e.match(r))throw new t(`Invalid cloud ID, expected ID of format ${r}.`)}(e.cloudId||"",null==r?void 0:r.cloudId),a(n,null==r?void 0:r.resourceOwner),u(p,null==r?void 0:r.resourceType),function(e,r){Object.entries(e).forEach(([e,s])=>{!function(e,r=new RegExp("[!a-zA-Z0-9\\-_.~@:;{}=]+(/[!a-zA-Z0-9\\-_.~@:;{}=]+)*"),s="resourceId"){let o=new RegExp(`^${r.source}$`);if(!e.match(o))throw new t(`Invalid ${s} - ${e}, expected ID of format ${o}.`)}(s,null==r?void 0:r[e],e)})}(d,null==r?void 0:r.resourceIdSegmentFormats),{qualifier:o,resourceOwner:n,resourceType:p,platformQualifier:i,cloudId:c,resourceId:l,resourceIdSegmentValues:d}}static ariSegmentValuesFromSlug(e,r,s){let o=new RegExp("^"+e.replace(/\{(.*?)\}/g,"(?<$1>.*?)")+"$").exec(r);if(!o)throw new t(`Segment '${r}' don't match expected slug: ${e}`);return s.forEach(r=>{var s;if(null==(s=o.groups)||!s[r])throw new t(`No value supplied for '${r}' based on slug ${e}`)}),o.groups||{}}},c=class extends i{static fromString(e,r){let t=this.getIdentifierSegments(e,4),[i="ati",n="cloud",c,l]=t;return o(i),s(n),a(c,null==r?void 0:r.resourceOwner),u(l,null==r?void 0:r.resourceType),{platformQualifier:n,resourceOwner:c,resourceType:l}}static fromOpts(e,r){let{qualifier:t,platformQualifier:i,resourceOwner:n,resourceType:c}=e;return o(t),s(i),a(n,null==r?void 0:r.resourceOwner),u(c,null==r?void 0:r.resourceType),{platformQualifier:i,resourceOwner:n,resourceType:c}}},l=class e{constructor(e,r,t){this._platformQualifier=e,this._resourceOwner=r,this._resourceType=t}get platformQualifier(){return this._platformQualifier}get resourceOwner(){return this._resourceOwner}get resourceType(){return this._resourceType}static create(r){return new e(r.platformQualifier||"cloud",r.resourceOwner,r.resourceType)}static parse(r,t){let s=c.fromString(r,t);return new e(s.platformQualifier,s.resourceOwner,s.resourceType)}toString(){return`ati:${this.platformQualifier}:${this.resourceOwner}:${this.resourceType}`}toJSON(){return this.toString()}toOpts(){return{platformQualifier:this._platformQualifier,resourceOwner:this._resourceOwner,resourceType:this._resourceType}}},d=class{constructor(e){this._ati=l.create({platformQualifier:e.platformQualifier||"cloud",resourceOwner:e.resourceOwner,resourceType:e.resourceType}),this._cloudId=""!==e.cloudId?e.cloudId:void 0,this._resourceId=e.resourceId}get platformQualifier(){return this._ati.platformQualifier}get cloudId(){return this._cloudId}get resourceOwner(){return this._ati.resourceOwner}get resourceType(){return this._ati.resourceType}get resourceId(){return this._resourceId}get ati(){return this._ati}equals(e){return this.toString()===e.toString()}toString(){return`ari:${this.platformQualifier}:${this.resourceOwner}:${this.cloudId||""}:${this.resourceType}/${this.resourceId}`}toJSON(){return this.toString()}toOpts(){return{platformQualifier:this.platformQualifier,resourceOwner:this.resourceOwner,cloudId:this.cloudId,resourceType:this.resourceType,resourceId:this.resourceId}}},p=class e extends d{constructor(e){super(e)}static create(r,t){let s={...r,resourceIdSegmentValues:{}},o=n.fromOpts(s,t);return new e(o)}static parse(r,t){let s=n.fromString(r,t);return new e(s)}static check(r){try{return e.parse(r.toString()),!0}catch(e){return!1}}asAnyAri(){return this}},I=class extends d{static check(e){try{return this.parse(e.toString()),!0}catch(e){return!1}}asAnyAri(){return p.parse(this.toString())}},f={qualifier:"ari",platformQualifier:"cloud",cloudId:new RegExp("^[a-zA-Z0-9_\\-.]{1,255}$"),resourceOwner:"compass",resourceType:"workspace",resourceIdSlug:"{workspaceId}",resourceIdSegmentFormats:{workspaceId:/[0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}/}},m=class e extends I{constructor(e){super(e),this._siteId=e.cloudId||"",this._workspaceId=e.resourceIdSegmentValues.workspaceId}get siteId(){return this._siteId}get workspaceId(){return this._workspaceId}static create(r){let t={qualifier:f.qualifier,platformQualifier:f.platformQualifier,cloudId:r.siteId,resourceOwner:f.resourceOwner,resourceType:f.resourceType,resourceId:`${r.workspaceId}`,resourceIdSegmentValues:{workspaceId:r.workspaceId}},s=n.fromOpts(t,f);return new e(s)}static parse(r){let t=n.fromString(r,f);return new e(t)}getVariables(){return{siteId:this.siteId,workspaceId:this.workspaceId}}},g={qualifier:"ari",platformQualifier:"cloud",cloudId:new RegExp("^[a-zA-Z0-9_\\-.]{1,255}$"),resourceOwner:"confluence",resourceType:"workspace",resourceIdSlug:"{activationId}",resourceIdSegmentFormats:{activationId:/[a-zA-Z0-9\-]+/}},w=class e extends I{constructor(e){super(e),this._siteId=e.cloudId||"",this._activationId=e.resourceIdSegmentValues.activationId}get siteId(){return this._siteId}get activationId(){return this._activationId}static create(r){let t={qualifier:g.qualifier,platformQualifier:g.platformQualifier,cloudId:r.siteId,resourceOwner:g.resourceOwner,resourceType:g.resourceType,resourceId:`${r.activationId}`,resourceIdSegmentValues:{activationId:r.activationId}},s=n.fromOpts(t,g);return new e(s)}static parse(r){let t=n.fromString(r,g);return new e(t)}getVariables(){return{siteId:this.siteId,activationId:this.activationId}}},h={qualifier:"ari",platformQualifier:"cloud",cloudId:new RegExp("^$"),resourceOwner:"ecosystem",resourceType:"app",resourceIdSlug:"{appId}",resourceIdSegmentFormats:{appId:/[0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}/}},v=class e extends I{constructor(e){super(e),this._appId=e.resourceIdSegmentValues.appId}get appId(){return this._appId}static create(r){let t={qualifier:h.qualifier,platformQualifier:h.platformQualifier,cloudId:void 0,resourceOwner:h.resourceOwner,resourceType:h.resourceType,resourceId:`${r.appId}`,resourceIdSegmentValues:{appId:r.appId}},s=n.fromOpts(t,h);return new e(s)}static parse(r){let t=n.fromString(r,h);return new e(t)}getVariables(){return{appId:this.appId}}},y={qualifier:"ari",platformQualifier:"cloud",cloudId:new RegExp("^$"),resourceOwner:"ecosystem",resourceType:"app-environment-version",resourceIdSlug:"{appId}/{environmentId}/{versionId}",resourceIdSegmentFormats:{appId:/[0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}/,environmentId:/[0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}/,versionId:/[0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}/}},S=class e extends I{constructor(e){super(e),this._appId=e.resourceIdSegmentValues.appId,this._environmentId=e.resourceIdSegmentValues.environmentId,this._versionId=e.resourceIdSegmentValues.versionId}get appId(){return this._appId}get environmentId(){return this._environmentId}get versionId(){return this._versionId}static create(r){let t={qualifier:y.qualifier,platformQualifier:y.platformQualifier,cloudId:void 0,resourceOwner:y.resourceOwner,resourceType:y.resourceType,resourceId:`${r.appId}/${r.environmentId}/${r.versionId}`,resourceIdSegmentValues:{appId:r.appId,environmentId:r.environmentId,versionId:r.versionId}},s=n.fromOpts(t,y);return new e(s)}static parse(r){let t=n.fromString(r,y);return new e(t)}getVariables(){return{appId:this.appId,environmentId:this.environmentId,versionId:this.versionId}}},O={qualifier:"ari",platformQualifier:"cloud",cloudId:new RegExp("^$"),resourceOwner:"ecosystem",resourceType:"app-placement",resourceIdSlug:"{placementType}/{placementId}",resourceIdSegmentFormats:{placementType:/(isolation-context|region|customer-data-plane)/,placementId:/[a-zA-Z0-9-._]+/}},T=class e extends I{constructor(e){super(e),this._placementType=e.resourceIdSegmentValues.placementType,this._placementId=e.resourceIdSegmentValues.placementId}get placementType(){return this._placementType}get placementId(){return this._placementId}static create(r){let t={qualifier:O.qualifier,platformQualifier:O.platformQualifier,cloudId:void 0,resourceOwner:O.resourceOwner,resourceType:O.resourceType,resourceId:`${r.placementType}/${r.placementId}`,resourceIdSegmentValues:{placementType:r.placementType,placementId:r.placementId}},s=n.fromOpts(t,O);return new e(s)}static parse(r){let t=n.fromString(r,O);return new e(t)}getVariables(){return{placementType:this.placementType,placementId:this.placementId}}},_={qualifier:"ari",platformQualifier:"cloud",cloudId:new RegExp("^$"),resourceOwner:"graph",resourceType:"workspace",resourceIdSlug:"{workspaceId}",resourceIdSegmentFormats:{workspaceId:/[0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}/}},$=class e extends I{constructor(e){super(e),this._workspaceId=e.resourceIdSegmentValues.workspaceId}get workspaceId(){return this._workspaceId}static create(r){let t={qualifier:_.qualifier,platformQualifier:_.platformQualifier,cloudId:void 0,resourceOwner:_.resourceOwner,resourceType:_.resourceType,resourceId:`${r.workspaceId}`,resourceIdSegmentValues:{workspaceId:r.workspaceId}},s=n.fromOpts(t,_);return new e(s)}static parse(r){let t=n.fromString(r,_);return new e(t)}getVariables(){return{workspaceId:this.workspaceId}}},Q={qualifier:"ari",platformQualifier:"cloud",cloudId:new RegExp("^[a-zA-Z0-9_\\-.]{1,255}$"),resourceOwner:"jira",resourceType:"workspace",resourceIdSlug:"{activationId}",resourceIdSegmentFormats:{activationId:/[a-zA-Z0-9\-]+/}},k=class e extends I{constructor(e){super(e),this._siteId=e.cloudId||"",this._activationId=e.resourceIdSegmentValues.activationId}get siteId(){return this._siteId}get activationId(){return this._activationId}static create(r){let t={qualifier:Q.qualifier,platformQualifier:Q.platformQualifier,cloudId:r.siteId,resourceOwner:Q.resourceOwner,resourceType:Q.resourceType,resourceId:`${r.activationId}`,resourceIdSegmentValues:{activationId:r.activationId}},s=n.fromOpts(t,Q);return new e(s)}static parse(r){let t=n.fromString(r,Q);return new e(t)}getVariables(){return{siteId:this.siteId,activationId:this.activationId}}};module.exports=r})();

/***/ },

/***/ 1549
(module, __unused_webpack_exports, __webpack_require__) {

var hashClear = __webpack_require__(2032),
    hashDelete = __webpack_require__(3862),
    hashGet = __webpack_require__(6721),
    hashHas = __webpack_require__(2749),
    hashSet = __webpack_require__(5749);

/**
 * Creates a hash object.
 *
 * @private
 * @constructor
 * @param {Array} [entries] The key-value pairs to cache.
 */
function Hash(entries) {
  var index = -1,
      length = entries == null ? 0 : entries.length;

  this.clear();
  while (++index < length) {
    var entry = entries[index];
    this.set(entry[0], entry[1]);
  }
}

// Add methods to `Hash`.
Hash.prototype.clear = hashClear;
Hash.prototype['delete'] = hashDelete;
Hash.prototype.get = hashGet;
Hash.prototype.has = hashHas;
Hash.prototype.set = hashSet;

module.exports = Hash;


/***/ },

/***/ 79
(module, __unused_webpack_exports, __webpack_require__) {

var listCacheClear = __webpack_require__(3702),
    listCacheDelete = __webpack_require__(80),
    listCacheGet = __webpack_require__(4739),
    listCacheHas = __webpack_require__(8655),
    listCacheSet = __webpack_require__(1175);

/**
 * Creates an list cache object.
 *
 * @private
 * @constructor
 * @param {Array} [entries] The key-value pairs to cache.
 */
function ListCache(entries) {
  var index = -1,
      length = entries == null ? 0 : entries.length;

  this.clear();
  while (++index < length) {
    var entry = entries[index];
    this.set(entry[0], entry[1]);
  }
}

// Add methods to `ListCache`.
ListCache.prototype.clear = listCacheClear;
ListCache.prototype['delete'] = listCacheDelete;
ListCache.prototype.get = listCacheGet;
ListCache.prototype.has = listCacheHas;
ListCache.prototype.set = listCacheSet;

module.exports = ListCache;


/***/ },

/***/ 8223
(module, __unused_webpack_exports, __webpack_require__) {

var getNative = __webpack_require__(6110),
    root = __webpack_require__(9325);

/* Built-in method references that are verified to be native. */
var Map = getNative(root, 'Map');

module.exports = Map;


/***/ },

/***/ 3661
(module, __unused_webpack_exports, __webpack_require__) {

var mapCacheClear = __webpack_require__(3040),
    mapCacheDelete = __webpack_require__(7670),
    mapCacheGet = __webpack_require__(289),
    mapCacheHas = __webpack_require__(4509),
    mapCacheSet = __webpack_require__(2949);

/**
 * Creates a map cache object to store key-value pairs.
 *
 * @private
 * @constructor
 * @param {Array} [entries] The key-value pairs to cache.
 */
function MapCache(entries) {
  var index = -1,
      length = entries == null ? 0 : entries.length;

  this.clear();
  while (++index < length) {
    var entry = entries[index];
    this.set(entry[0], entry[1]);
  }
}

// Add methods to `MapCache`.
MapCache.prototype.clear = mapCacheClear;
MapCache.prototype['delete'] = mapCacheDelete;
MapCache.prototype.get = mapCacheGet;
MapCache.prototype.has = mapCacheHas;
MapCache.prototype.set = mapCacheSet;

module.exports = MapCache;


/***/ },

/***/ 1873
(module, __unused_webpack_exports, __webpack_require__) {

var root = __webpack_require__(9325);

/** Built-in value references. */
var Symbol = root.Symbol;

module.exports = Symbol;


/***/ },

/***/ 4932
(module) {

/**
 * A specialized version of `_.map` for arrays without support for iteratee
 * shorthands.
 *
 * @private
 * @param {Array} [array] The array to iterate over.
 * @param {Function} iteratee The function invoked per iteration.
 * @returns {Array} Returns the new mapped array.
 */
function arrayMap(array, iteratee) {
  var index = -1,
      length = array == null ? 0 : array.length,
      result = Array(length);

  while (++index < length) {
    result[index] = iteratee(array[index], index, array);
  }
  return result;
}

module.exports = arrayMap;


/***/ },

/***/ 6025
(module, __unused_webpack_exports, __webpack_require__) {

var eq = __webpack_require__(5288);

/**
 * Gets the index at which the `key` is found in `array` of key-value pairs.
 *
 * @private
 * @param {Array} array The array to inspect.
 * @param {*} key The key to search for.
 * @returns {number} Returns the index of the matched value, else `-1`.
 */
function assocIndexOf(array, key) {
  var length = array.length;
  while (length--) {
    if (eq(array[length][0], key)) {
      return length;
    }
  }
  return -1;
}

module.exports = assocIndexOf;


/***/ },

/***/ 7422
(module, __unused_webpack_exports, __webpack_require__) {

var castPath = __webpack_require__(1769),
    toKey = __webpack_require__(7797);

/**
 * The base implementation of `_.get` without support for default values.
 *
 * @private
 * @param {Object} object The object to query.
 * @param {Array|string} path The path of the property to get.
 * @returns {*} Returns the resolved value.
 */
function baseGet(object, path) {
  path = castPath(path, object);

  var index = 0,
      length = path.length;

  while (object != null && index < length) {
    object = object[toKey(path[index++])];
  }
  return (index && index == length) ? object : undefined;
}

module.exports = baseGet;


/***/ },

/***/ 2552
(module, __unused_webpack_exports, __webpack_require__) {

var Symbol = __webpack_require__(1873),
    getRawTag = __webpack_require__(659),
    objectToString = __webpack_require__(9350);

/** `Object#toString` result references. */
var nullTag = '[object Null]',
    undefinedTag = '[object Undefined]';

/** Built-in value references. */
var symToStringTag = Symbol ? Symbol.toStringTag : undefined;

/**
 * The base implementation of `getTag` without fallbacks for buggy environments.
 *
 * @private
 * @param {*} value The value to query.
 * @returns {string} Returns the `toStringTag`.
 */
function baseGetTag(value) {
  if (value == null) {
    return value === undefined ? undefinedTag : nullTag;
  }
  return (symToStringTag && symToStringTag in Object(value))
    ? getRawTag(value)
    : objectToString(value);
}

module.exports = baseGetTag;


/***/ },

/***/ 5083
(module, __unused_webpack_exports, __webpack_require__) {

var isFunction = __webpack_require__(1882),
    isMasked = __webpack_require__(7296),
    isObject = __webpack_require__(3805),
    toSource = __webpack_require__(7473);

/**
 * Used to match `RegExp`
 * [syntax characters](http://ecma-international.org/ecma-262/7.0/#sec-patterns).
 */
var reRegExpChar = /[\\^$.*+?()[\]{}|]/g;

/** Used to detect host constructors (Safari). */
var reIsHostCtor = /^\[object .+?Constructor\]$/;

/** Used for built-in method references. */
var funcProto = Function.prototype,
    objectProto = Object.prototype;

/** Used to resolve the decompiled source of functions. */
var funcToString = funcProto.toString;

/** Used to check objects for own properties. */
var hasOwnProperty = objectProto.hasOwnProperty;

/** Used to detect if a method is native. */
var reIsNative = RegExp('^' +
  funcToString.call(hasOwnProperty).replace(reRegExpChar, '\\$&')
  .replace(/hasOwnProperty|(function).*?(?=\\\()| for .+?(?=\\\])/g, '$1.*?') + '$'
);

/**
 * The base implementation of `_.isNative` without bad shim checks.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a native function,
 *  else `false`.
 */
function baseIsNative(value) {
  if (!isObject(value) || isMasked(value)) {
    return false;
  }
  var pattern = isFunction(value) ? reIsNative : reIsHostCtor;
  return pattern.test(toSource(value));
}

module.exports = baseIsNative;


/***/ },

/***/ 7556
(module, __unused_webpack_exports, __webpack_require__) {

var Symbol = __webpack_require__(1873),
    arrayMap = __webpack_require__(4932),
    isArray = __webpack_require__(6449),
    isSymbol = __webpack_require__(4394);

/** Used as references for various `Number` constants. */
var INFINITY = 1 / 0;

/** Used to convert symbols to primitives and strings. */
var symbolProto = Symbol ? Symbol.prototype : undefined,
    symbolToString = symbolProto ? symbolProto.toString : undefined;

/**
 * The base implementation of `_.toString` which doesn't convert nullish
 * values to empty strings.
 *
 * @private
 * @param {*} value The value to process.
 * @returns {string} Returns the string.
 */
function baseToString(value) {
  // Exit early for strings to avoid a performance hit in some environments.
  if (typeof value == 'string') {
    return value;
  }
  if (isArray(value)) {
    // Recursively convert values (susceptible to call stack limits).
    return arrayMap(value, baseToString) + '';
  }
  if (isSymbol(value)) {
    return symbolToString ? symbolToString.call(value) : '';
  }
  var result = (value + '');
  return (result == '0' && (1 / value) == -INFINITY) ? '-0' : result;
}

module.exports = baseToString;


/***/ },

/***/ 1769
(module, __unused_webpack_exports, __webpack_require__) {

var isArray = __webpack_require__(6449),
    isKey = __webpack_require__(8586),
    stringToPath = __webpack_require__(1802),
    toString = __webpack_require__(3222);

/**
 * Casts `value` to a path array if it's not one.
 *
 * @private
 * @param {*} value The value to inspect.
 * @param {Object} [object] The object to query keys on.
 * @returns {Array} Returns the cast property path array.
 */
function castPath(value, object) {
  if (isArray(value)) {
    return value;
  }
  return isKey(value, object) ? [value] : stringToPath(toString(value));
}

module.exports = castPath;


/***/ },

/***/ 5481
(module, __unused_webpack_exports, __webpack_require__) {

var root = __webpack_require__(9325);

/** Used to detect overreaching core-js shims. */
var coreJsData = root['__core-js_shared__'];

module.exports = coreJsData;


/***/ },

/***/ 4840
(module) {

/** Detect free variable `global` from Node.js. */
var freeGlobal = typeof global == 'object' && global && global.Object === Object && global;

module.exports = freeGlobal;


/***/ },

/***/ 2651
(module, __unused_webpack_exports, __webpack_require__) {

var isKeyable = __webpack_require__(4218);

/**
 * Gets the data for `map`.
 *
 * @private
 * @param {Object} map The map to query.
 * @param {string} key The reference key.
 * @returns {*} Returns the map data.
 */
function getMapData(map, key) {
  var data = map.__data__;
  return isKeyable(key)
    ? data[typeof key == 'string' ? 'string' : 'hash']
    : data.map;
}

module.exports = getMapData;


/***/ },

/***/ 6110
(module, __unused_webpack_exports, __webpack_require__) {

var baseIsNative = __webpack_require__(5083),
    getValue = __webpack_require__(392);

/**
 * Gets the native function at `key` of `object`.
 *
 * @private
 * @param {Object} object The object to query.
 * @param {string} key The key of the method to get.
 * @returns {*} Returns the function if it's native, else `undefined`.
 */
function getNative(object, key) {
  var value = getValue(object, key);
  return baseIsNative(value) ? value : undefined;
}

module.exports = getNative;


/***/ },

/***/ 659
(module, __unused_webpack_exports, __webpack_require__) {

var Symbol = __webpack_require__(1873);

/** Used for built-in method references. */
var objectProto = Object.prototype;

/** Used to check objects for own properties. */
var hasOwnProperty = objectProto.hasOwnProperty;

/**
 * Used to resolve the
 * [`toStringTag`](http://ecma-international.org/ecma-262/7.0/#sec-object.prototype.tostring)
 * of values.
 */
var nativeObjectToString = objectProto.toString;

/** Built-in value references. */
var symToStringTag = Symbol ? Symbol.toStringTag : undefined;

/**
 * A specialized version of `baseGetTag` which ignores `Symbol.toStringTag` values.
 *
 * @private
 * @param {*} value The value to query.
 * @returns {string} Returns the raw `toStringTag`.
 */
function getRawTag(value) {
  var isOwn = hasOwnProperty.call(value, symToStringTag),
      tag = value[symToStringTag];

  try {
    value[symToStringTag] = undefined;
    var unmasked = true;
  } catch (e) {}

  var result = nativeObjectToString.call(value);
  if (unmasked) {
    if (isOwn) {
      value[symToStringTag] = tag;
    } else {
      delete value[symToStringTag];
    }
  }
  return result;
}

module.exports = getRawTag;


/***/ },

/***/ 392
(module) {

/**
 * Gets the value at `key` of `object`.
 *
 * @private
 * @param {Object} [object] The object to query.
 * @param {string} key The key of the property to get.
 * @returns {*} Returns the property value.
 */
function getValue(object, key) {
  return object == null ? undefined : object[key];
}

module.exports = getValue;


/***/ },

/***/ 2032
(module, __unused_webpack_exports, __webpack_require__) {

var nativeCreate = __webpack_require__(1042);

/**
 * Removes all key-value entries from the hash.
 *
 * @private
 * @name clear
 * @memberOf Hash
 */
function hashClear() {
  this.__data__ = nativeCreate ? nativeCreate(null) : {};
  this.size = 0;
}

module.exports = hashClear;


/***/ },

/***/ 3862
(module) {

/**
 * Removes `key` and its value from the hash.
 *
 * @private
 * @name delete
 * @memberOf Hash
 * @param {Object} hash The hash to modify.
 * @param {string} key The key of the value to remove.
 * @returns {boolean} Returns `true` if the entry was removed, else `false`.
 */
function hashDelete(key) {
  var result = this.has(key) && delete this.__data__[key];
  this.size -= result ? 1 : 0;
  return result;
}

module.exports = hashDelete;


/***/ },

/***/ 6721
(module, __unused_webpack_exports, __webpack_require__) {

var nativeCreate = __webpack_require__(1042);

/** Used to stand-in for `undefined` hash values. */
var HASH_UNDEFINED = '__lodash_hash_undefined__';

/** Used for built-in method references. */
var objectProto = Object.prototype;

/** Used to check objects for own properties. */
var hasOwnProperty = objectProto.hasOwnProperty;

/**
 * Gets the hash value for `key`.
 *
 * @private
 * @name get
 * @memberOf Hash
 * @param {string} key The key of the value to get.
 * @returns {*} Returns the entry value.
 */
function hashGet(key) {
  var data = this.__data__;
  if (nativeCreate) {
    var result = data[key];
    return result === HASH_UNDEFINED ? undefined : result;
  }
  return hasOwnProperty.call(data, key) ? data[key] : undefined;
}

module.exports = hashGet;


/***/ },

/***/ 2749
(module, __unused_webpack_exports, __webpack_require__) {

var nativeCreate = __webpack_require__(1042);

/** Used for built-in method references. */
var objectProto = Object.prototype;

/** Used to check objects for own properties. */
var hasOwnProperty = objectProto.hasOwnProperty;

/**
 * Checks if a hash value for `key` exists.
 *
 * @private
 * @name has
 * @memberOf Hash
 * @param {string} key The key of the entry to check.
 * @returns {boolean} Returns `true` if an entry for `key` exists, else `false`.
 */
function hashHas(key) {
  var data = this.__data__;
  return nativeCreate ? (data[key] !== undefined) : hasOwnProperty.call(data, key);
}

module.exports = hashHas;


/***/ },

/***/ 5749
(module, __unused_webpack_exports, __webpack_require__) {

var nativeCreate = __webpack_require__(1042);

/** Used to stand-in for `undefined` hash values. */
var HASH_UNDEFINED = '__lodash_hash_undefined__';

/**
 * Sets the hash `key` to `value`.
 *
 * @private
 * @name set
 * @memberOf Hash
 * @param {string} key The key of the value to set.
 * @param {*} value The value to set.
 * @returns {Object} Returns the hash instance.
 */
function hashSet(key, value) {
  var data = this.__data__;
  this.size += this.has(key) ? 0 : 1;
  data[key] = (nativeCreate && value === undefined) ? HASH_UNDEFINED : value;
  return this;
}

module.exports = hashSet;


/***/ },

/***/ 8586
(module, __unused_webpack_exports, __webpack_require__) {

var isArray = __webpack_require__(6449),
    isSymbol = __webpack_require__(4394);

/** Used to match property names within property paths. */
var reIsDeepProp = /\.|\[(?:[^[\]]*|(["'])(?:(?!\1)[^\\]|\\.)*?\1)\]/,
    reIsPlainProp = /^\w*$/;

/**
 * Checks if `value` is a property name and not a property path.
 *
 * @private
 * @param {*} value The value to check.
 * @param {Object} [object] The object to query keys on.
 * @returns {boolean} Returns `true` if `value` is a property name, else `false`.
 */
function isKey(value, object) {
  if (isArray(value)) {
    return false;
  }
  var type = typeof value;
  if (type == 'number' || type == 'symbol' || type == 'boolean' ||
      value == null || isSymbol(value)) {
    return true;
  }
  return reIsPlainProp.test(value) || !reIsDeepProp.test(value) ||
    (object != null && value in Object(object));
}

module.exports = isKey;


/***/ },

/***/ 4218
(module) {

/**
 * Checks if `value` is suitable for use as unique object key.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is suitable, else `false`.
 */
function isKeyable(value) {
  var type = typeof value;
  return (type == 'string' || type == 'number' || type == 'symbol' || type == 'boolean')
    ? (value !== '__proto__')
    : (value === null);
}

module.exports = isKeyable;


/***/ },

/***/ 7296
(module, __unused_webpack_exports, __webpack_require__) {

var coreJsData = __webpack_require__(5481);

/** Used to detect methods masquerading as native. */
var maskSrcKey = (function() {
  var uid = /[^.]+$/.exec(coreJsData && coreJsData.keys && coreJsData.keys.IE_PROTO || '');
  return uid ? ('Symbol(src)_1.' + uid) : '';
}());

/**
 * Checks if `func` has its source masked.
 *
 * @private
 * @param {Function} func The function to check.
 * @returns {boolean} Returns `true` if `func` is masked, else `false`.
 */
function isMasked(func) {
  return !!maskSrcKey && (maskSrcKey in func);
}

module.exports = isMasked;


/***/ },

/***/ 3702
(module) {

/**
 * Removes all key-value entries from the list cache.
 *
 * @private
 * @name clear
 * @memberOf ListCache
 */
function listCacheClear() {
  this.__data__ = [];
  this.size = 0;
}

module.exports = listCacheClear;


/***/ },

/***/ 80
(module, __unused_webpack_exports, __webpack_require__) {

var assocIndexOf = __webpack_require__(6025);

/** Used for built-in method references. */
var arrayProto = Array.prototype;

/** Built-in value references. */
var splice = arrayProto.splice;

/**
 * Removes `key` and its value from the list cache.
 *
 * @private
 * @name delete
 * @memberOf ListCache
 * @param {string} key The key of the value to remove.
 * @returns {boolean} Returns `true` if the entry was removed, else `false`.
 */
function listCacheDelete(key) {
  var data = this.__data__,
      index = assocIndexOf(data, key);

  if (index < 0) {
    return false;
  }
  var lastIndex = data.length - 1;
  if (index == lastIndex) {
    data.pop();
  } else {
    splice.call(data, index, 1);
  }
  --this.size;
  return true;
}

module.exports = listCacheDelete;


/***/ },

/***/ 4739
(module, __unused_webpack_exports, __webpack_require__) {

var assocIndexOf = __webpack_require__(6025);

/**
 * Gets the list cache value for `key`.
 *
 * @private
 * @name get
 * @memberOf ListCache
 * @param {string} key The key of the value to get.
 * @returns {*} Returns the entry value.
 */
function listCacheGet(key) {
  var data = this.__data__,
      index = assocIndexOf(data, key);

  return index < 0 ? undefined : data[index][1];
}

module.exports = listCacheGet;


/***/ },

/***/ 8655
(module, __unused_webpack_exports, __webpack_require__) {

var assocIndexOf = __webpack_require__(6025);

/**
 * Checks if a list cache value for `key` exists.
 *
 * @private
 * @name has
 * @memberOf ListCache
 * @param {string} key The key of the entry to check.
 * @returns {boolean} Returns `true` if an entry for `key` exists, else `false`.
 */
function listCacheHas(key) {
  return assocIndexOf(this.__data__, key) > -1;
}

module.exports = listCacheHas;


/***/ },

/***/ 1175
(module, __unused_webpack_exports, __webpack_require__) {

var assocIndexOf = __webpack_require__(6025);

/**
 * Sets the list cache `key` to `value`.
 *
 * @private
 * @name set
 * @memberOf ListCache
 * @param {string} key The key of the value to set.
 * @param {*} value The value to set.
 * @returns {Object} Returns the list cache instance.
 */
function listCacheSet(key, value) {
  var data = this.__data__,
      index = assocIndexOf(data, key);

  if (index < 0) {
    ++this.size;
    data.push([key, value]);
  } else {
    data[index][1] = value;
  }
  return this;
}

module.exports = listCacheSet;


/***/ },

/***/ 3040
(module, __unused_webpack_exports, __webpack_require__) {

var Hash = __webpack_require__(1549),
    ListCache = __webpack_require__(79),
    Map = __webpack_require__(8223);

/**
 * Removes all key-value entries from the map.
 *
 * @private
 * @name clear
 * @memberOf MapCache
 */
function mapCacheClear() {
  this.size = 0;
  this.__data__ = {
    'hash': new Hash,
    'map': new (Map || ListCache),
    'string': new Hash
  };
}

module.exports = mapCacheClear;


/***/ },

/***/ 7670
(module, __unused_webpack_exports, __webpack_require__) {

var getMapData = __webpack_require__(2651);

/**
 * Removes `key` and its value from the map.
 *
 * @private
 * @name delete
 * @memberOf MapCache
 * @param {string} key The key of the value to remove.
 * @returns {boolean} Returns `true` if the entry was removed, else `false`.
 */
function mapCacheDelete(key) {
  var result = getMapData(this, key)['delete'](key);
  this.size -= result ? 1 : 0;
  return result;
}

module.exports = mapCacheDelete;


/***/ },

/***/ 289
(module, __unused_webpack_exports, __webpack_require__) {

var getMapData = __webpack_require__(2651);

/**
 * Gets the map value for `key`.
 *
 * @private
 * @name get
 * @memberOf MapCache
 * @param {string} key The key of the value to get.
 * @returns {*} Returns the entry value.
 */
function mapCacheGet(key) {
  return getMapData(this, key).get(key);
}

module.exports = mapCacheGet;


/***/ },

/***/ 4509
(module, __unused_webpack_exports, __webpack_require__) {

var getMapData = __webpack_require__(2651);

/**
 * Checks if a map value for `key` exists.
 *
 * @private
 * @name has
 * @memberOf MapCache
 * @param {string} key The key of the entry to check.
 * @returns {boolean} Returns `true` if an entry for `key` exists, else `false`.
 */
function mapCacheHas(key) {
  return getMapData(this, key).has(key);
}

module.exports = mapCacheHas;


/***/ },

/***/ 2949
(module, __unused_webpack_exports, __webpack_require__) {

var getMapData = __webpack_require__(2651);

/**
 * Sets the map `key` to `value`.
 *
 * @private
 * @name set
 * @memberOf MapCache
 * @param {string} key The key of the value to set.
 * @param {*} value The value to set.
 * @returns {Object} Returns the map cache instance.
 */
function mapCacheSet(key, value) {
  var data = getMapData(this, key),
      size = data.size;

  data.set(key, value);
  this.size += data.size == size ? 0 : 1;
  return this;
}

module.exports = mapCacheSet;


/***/ },

/***/ 2224
(module, __unused_webpack_exports, __webpack_require__) {

var memoize = __webpack_require__(104);

/** Used as the maximum memoize cache size. */
var MAX_MEMOIZE_SIZE = 500;

/**
 * A specialized version of `_.memoize` which clears the memoized function's
 * cache when it exceeds `MAX_MEMOIZE_SIZE`.
 *
 * @private
 * @param {Function} func The function to have its output memoized.
 * @returns {Function} Returns the new memoized function.
 */
function memoizeCapped(func) {
  var result = memoize(func, function(key) {
    if (cache.size === MAX_MEMOIZE_SIZE) {
      cache.clear();
    }
    return key;
  });

  var cache = result.cache;
  return result;
}

module.exports = memoizeCapped;


/***/ },

/***/ 1042
(module, __unused_webpack_exports, __webpack_require__) {

var getNative = __webpack_require__(6110);

/* Built-in method references that are verified to be native. */
var nativeCreate = getNative(Object, 'create');

module.exports = nativeCreate;


/***/ },

/***/ 9350
(module) {

/** Used for built-in method references. */
var objectProto = Object.prototype;

/**
 * Used to resolve the
 * [`toStringTag`](http://ecma-international.org/ecma-262/7.0/#sec-object.prototype.tostring)
 * of values.
 */
var nativeObjectToString = objectProto.toString;

/**
 * Converts `value` to a string using `Object.prototype.toString`.
 *
 * @private
 * @param {*} value The value to convert.
 * @returns {string} Returns the converted string.
 */
function objectToString(value) {
  return nativeObjectToString.call(value);
}

module.exports = objectToString;


/***/ },

/***/ 9325
(module, __unused_webpack_exports, __webpack_require__) {

var freeGlobal = __webpack_require__(4840);

/** Detect free variable `self`. */
var freeSelf = typeof self == 'object' && self && self.Object === Object && self;

/** Used as a reference to the global object. */
var root = freeGlobal || freeSelf || Function('return this')();

module.exports = root;


/***/ },

/***/ 1802
(module, __unused_webpack_exports, __webpack_require__) {

var memoizeCapped = __webpack_require__(2224);

/** Used to match property names within property paths. */
var rePropName = /[^.[\]]+|\[(?:(-?\d+(?:\.\d+)?)|(["'])((?:(?!\2)[^\\]|\\.)*?)\2)\]|(?=(?:\.|\[\])(?:\.|\[\]|$))/g;

/** Used to match backslashes in property paths. */
var reEscapeChar = /\\(\\)?/g;

/**
 * Converts `string` to a property path array.
 *
 * @private
 * @param {string} string The string to convert.
 * @returns {Array} Returns the property path array.
 */
var stringToPath = memoizeCapped(function(string) {
  var result = [];
  if (string.charCodeAt(0) === 46 /* . */) {
    result.push('');
  }
  string.replace(rePropName, function(match, number, quote, subString) {
    result.push(quote ? subString.replace(reEscapeChar, '$1') : (number || match));
  });
  return result;
});

module.exports = stringToPath;


/***/ },

/***/ 7797
(module, __unused_webpack_exports, __webpack_require__) {

var isSymbol = __webpack_require__(4394);

/** Used as references for various `Number` constants. */
var INFINITY = 1 / 0;

/**
 * Converts `value` to a string key if it's not a string or symbol.
 *
 * @private
 * @param {*} value The value to inspect.
 * @returns {string|symbol} Returns the key.
 */
function toKey(value) {
  if (typeof value == 'string' || isSymbol(value)) {
    return value;
  }
  var result = (value + '');
  return (result == '0' && (1 / value) == -INFINITY) ? '-0' : result;
}

module.exports = toKey;


/***/ },

/***/ 7473
(module) {

/** Used for built-in method references. */
var funcProto = Function.prototype;

/** Used to resolve the decompiled source of functions. */
var funcToString = funcProto.toString;

/**
 * Converts `func` to its source code.
 *
 * @private
 * @param {Function} func The function to convert.
 * @returns {string} Returns the source code.
 */
function toSource(func) {
  if (func != null) {
    try {
      return funcToString.call(func);
    } catch (e) {}
    try {
      return (func + '');
    } catch (e) {}
  }
  return '';
}

module.exports = toSource;


/***/ },

/***/ 5288
(module) {

/**
 * Performs a
 * [`SameValueZero`](http://ecma-international.org/ecma-262/7.0/#sec-samevaluezero)
 * comparison between two values to determine if they are equivalent.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to compare.
 * @param {*} other The other value to compare.
 * @returns {boolean} Returns `true` if the values are equivalent, else `false`.
 * @example
 *
 * var object = { 'a': 1 };
 * var other = { 'a': 1 };
 *
 * _.eq(object, object);
 * // => true
 *
 * _.eq(object, other);
 * // => false
 *
 * _.eq('a', 'a');
 * // => true
 *
 * _.eq('a', Object('a'));
 * // => false
 *
 * _.eq(NaN, NaN);
 * // => true
 */
function eq(value, other) {
  return value === other || (value !== value && other !== other);
}

module.exports = eq;


/***/ },

/***/ 8156
(module, __unused_webpack_exports, __webpack_require__) {

var baseGet = __webpack_require__(7422);

/**
 * Gets the value at `path` of `object`. If the resolved value is
 * `undefined`, the `defaultValue` is returned in its place.
 *
 * @static
 * @memberOf _
 * @since 3.7.0
 * @category Object
 * @param {Object} object The object to query.
 * @param {Array|string} path The path of the property to get.
 * @param {*} [defaultValue] The value returned for `undefined` resolved values.
 * @returns {*} Returns the resolved value.
 * @example
 *
 * var object = { 'a': [{ 'b': { 'c': 3 } }] };
 *
 * _.get(object, 'a[0].b.c');
 * // => 3
 *
 * _.get(object, ['a', '0', 'b', 'c']);
 * // => 3
 *
 * _.get(object, 'a.b.c', 'default');
 * // => 'default'
 */
function get(object, path, defaultValue) {
  var result = object == null ? undefined : baseGet(object, path);
  return result === undefined ? defaultValue : result;
}

module.exports = get;


/***/ },

/***/ 6449
(module) {

/**
 * Checks if `value` is classified as an `Array` object.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is an array, else `false`.
 * @example
 *
 * _.isArray([1, 2, 3]);
 * // => true
 *
 * _.isArray(document.body.children);
 * // => false
 *
 * _.isArray('abc');
 * // => false
 *
 * _.isArray(_.noop);
 * // => false
 */
var isArray = Array.isArray;

module.exports = isArray;


/***/ },

/***/ 1882
(module, __unused_webpack_exports, __webpack_require__) {

var baseGetTag = __webpack_require__(2552),
    isObject = __webpack_require__(3805);

/** `Object#toString` result references. */
var asyncTag = '[object AsyncFunction]',
    funcTag = '[object Function]',
    genTag = '[object GeneratorFunction]',
    proxyTag = '[object Proxy]';

/**
 * Checks if `value` is classified as a `Function` object.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a function, else `false`.
 * @example
 *
 * _.isFunction(_);
 * // => true
 *
 * _.isFunction(/abc/);
 * // => false
 */
function isFunction(value) {
  if (!isObject(value)) {
    return false;
  }
  // The use of `Object#toString` avoids issues with the `typeof` operator
  // in Safari 9 which returns 'object' for typed arrays and other constructors.
  var tag = baseGetTag(value);
  return tag == funcTag || tag == genTag || tag == asyncTag || tag == proxyTag;
}

module.exports = isFunction;


/***/ },

/***/ 3805
(module) {

/**
 * Checks if `value` is the
 * [language type](http://www.ecma-international.org/ecma-262/7.0/#sec-ecmascript-language-types)
 * of `Object`. (e.g. arrays, functions, objects, regexes, `new Number(0)`, and `new String('')`)
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is an object, else `false`.
 * @example
 *
 * _.isObject({});
 * // => true
 *
 * _.isObject([1, 2, 3]);
 * // => true
 *
 * _.isObject(_.noop);
 * // => true
 *
 * _.isObject(null);
 * // => false
 */
function isObject(value) {
  var type = typeof value;
  return value != null && (type == 'object' || type == 'function');
}

module.exports = isObject;


/***/ },

/***/ 346
(module) {

/**
 * Checks if `value` is object-like. A value is object-like if it's not `null`
 * and has a `typeof` result of "object".
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is object-like, else `false`.
 * @example
 *
 * _.isObjectLike({});
 * // => true
 *
 * _.isObjectLike([1, 2, 3]);
 * // => true
 *
 * _.isObjectLike(_.noop);
 * // => false
 *
 * _.isObjectLike(null);
 * // => false
 */
function isObjectLike(value) {
  return value != null && typeof value == 'object';
}

module.exports = isObjectLike;


/***/ },

/***/ 4394
(module, __unused_webpack_exports, __webpack_require__) {

var baseGetTag = __webpack_require__(2552),
    isObjectLike = __webpack_require__(346);

/** `Object#toString` result references. */
var symbolTag = '[object Symbol]';

/**
 * Checks if `value` is classified as a `Symbol` primitive or object.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a symbol, else `false`.
 * @example
 *
 * _.isSymbol(Symbol.iterator);
 * // => true
 *
 * _.isSymbol('abc');
 * // => false
 */
function isSymbol(value) {
  return typeof value == 'symbol' ||
    (isObjectLike(value) && baseGetTag(value) == symbolTag);
}

module.exports = isSymbol;


/***/ },

/***/ 104
(module, __unused_webpack_exports, __webpack_require__) {

var MapCache = __webpack_require__(3661);

/** Error message constants. */
var FUNC_ERROR_TEXT = 'Expected a function';

/**
 * Creates a function that memoizes the result of `func`. If `resolver` is
 * provided, it determines the cache key for storing the result based on the
 * arguments provided to the memoized function. By default, the first argument
 * provided to the memoized function is used as the map cache key. The `func`
 * is invoked with the `this` binding of the memoized function.
 *
 * **Note:** The cache is exposed as the `cache` property on the memoized
 * function. Its creation may be customized by replacing the `_.memoize.Cache`
 * constructor with one whose instances implement the
 * [`Map`](http://ecma-international.org/ecma-262/7.0/#sec-properties-of-the-map-prototype-object)
 * method interface of `clear`, `delete`, `get`, `has`, and `set`.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Function
 * @param {Function} func The function to have its output memoized.
 * @param {Function} [resolver] The function to resolve the cache key.
 * @returns {Function} Returns the new memoized function.
 * @example
 *
 * var object = { 'a': 1, 'b': 2 };
 * var other = { 'c': 3, 'd': 4 };
 *
 * var values = _.memoize(_.values);
 * values(object);
 * // => [1, 2]
 *
 * values(other);
 * // => [3, 4]
 *
 * object.a = 2;
 * values(object);
 * // => [1, 2]
 *
 * // Modify the result cache.
 * values.cache.set(object, ['a', 'b']);
 * values(object);
 * // => ['a', 'b']
 *
 * // Replace `_.memoize.Cache`.
 * _.memoize.Cache = WeakMap;
 */
function memoize(func, resolver) {
  if (typeof func != 'function' || (resolver != null && typeof resolver != 'function')) {
    throw new TypeError(FUNC_ERROR_TEXT);
  }
  var memoized = function() {
    var args = arguments,
        key = resolver ? resolver.apply(this, args) : args[0],
        cache = memoized.cache;

    if (cache.has(key)) {
      return cache.get(key);
    }
    var result = func.apply(this, args);
    memoized.cache = cache.set(key, result) || cache;
    return result;
  };
  memoized.cache = new (memoize.Cache || MapCache);
  return memoized;
}

// Expose `MapCache`.
memoize.Cache = MapCache;

module.exports = memoize;


/***/ },

/***/ 3222
(module, __unused_webpack_exports, __webpack_require__) {

var baseToString = __webpack_require__(7556);

/**
 * Converts `value` to a string. An empty string is returned for `null`
 * and `undefined` values. The sign of `-0` is preserved.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to convert.
 * @returns {string} Returns the converted string.
 * @example
 *
 * _.toString(null);
 * // => ''
 *
 * _.toString(-0);
 * // => '-0'
 *
 * _.toString([1, 2, 3]);
 * // => '1,2,3'
 */
function toString(value) {
  return value == null ? '' : baseToString(value);
}

module.exports = toString;


/***/ },

/***/ 290
(module) {

"use strict";
module.exports = require("async_hooks");

/***/ },

/***/ 9896
(module) {

"use strict";
module.exports = require("fs");

/***/ },

/***/ 6928
(module) {

"use strict";
module.exports = require("path");

/***/ },

/***/ 1635
(__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   __exportStar: () => (/* binding */ __exportStar),
/* harmony export */   __importDefault: () => (/* binding */ __importDefault)
/* harmony export */ });
/* unused harmony exports __extends, __assign, __rest, __decorate, __param, __esDecorate, __runInitializers, __propKey, __setFunctionName, __metadata, __awaiter, __generator, __createBinding, __values, __read, __spread, __spreadArrays, __spreadArray, __await, __asyncGenerator, __asyncDelegator, __asyncValues, __makeTemplateObject, __importStar, __classPrivateFieldGet, __classPrivateFieldSet, __classPrivateFieldIn, __addDisposableResource, __disposeResources, __rewriteRelativeImportExtension */
/******************************************************************************
Copyright (c) Microsoft Corporation.

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
***************************************************************************** */
/* global Reflect, Promise, SuppressedError, Symbol, Iterator */

var extendStatics = function(d, b) {
  extendStatics = Object.setPrototypeOf ||
      ({ __proto__: [] } instanceof Array && function (d, b) { d.__proto__ = b; }) ||
      function (d, b) { for (var p in b) if (Object.prototype.hasOwnProperty.call(b, p)) d[p] = b[p]; };
  return extendStatics(d, b);
};

function __extends(d, b) {
  if (typeof b !== "function" && b !== null)
      throw new TypeError("Class extends value " + String(b) + " is not a constructor or null");
  extendStatics(d, b);
  function __() { this.constructor = d; }
  d.prototype = b === null ? Object.create(b) : (__.prototype = b.prototype, new __());
}

var __assign = function() {
  __assign = Object.assign || function __assign(t) {
      for (var s, i = 1, n = arguments.length; i < n; i++) {
          s = arguments[i];
          for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p)) t[p] = s[p];
      }
      return t;
  }
  return __assign.apply(this, arguments);
}

function __rest(s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0)
      t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function")
      for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
          if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i]))
              t[p[i]] = s[p[i]];
      }
  return t;
}

function __decorate(decorators, target, key, desc) {
  var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
  if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
  else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
  return c > 3 && r && Object.defineProperty(target, key, r), r;
}

function __param(paramIndex, decorator) {
  return function (target, key) { decorator(target, key, paramIndex); }
}

function __esDecorate(ctor, descriptorIn, decorators, contextIn, initializers, extraInitializers) {
  function accept(f) { if (f !== void 0 && typeof f !== "function") throw new TypeError("Function expected"); return f; }
  var kind = contextIn.kind, key = kind === "getter" ? "get" : kind === "setter" ? "set" : "value";
  var target = !descriptorIn && ctor ? contextIn["static"] ? ctor : ctor.prototype : null;
  var descriptor = descriptorIn || (target ? Object.getOwnPropertyDescriptor(target, contextIn.name) : {});
  var _, done = false;
  for (var i = decorators.length - 1; i >= 0; i--) {
      var context = {};
      for (var p in contextIn) context[p] = p === "access" ? {} : contextIn[p];
      for (var p in contextIn.access) context.access[p] = contextIn.access[p];
      context.addInitializer = function (f) { if (done) throw new TypeError("Cannot add initializers after decoration has completed"); extraInitializers.push(accept(f || null)); };
      var result = (0, decorators[i])(kind === "accessor" ? { get: descriptor.get, set: descriptor.set } : descriptor[key], context);
      if (kind === "accessor") {
          if (result === void 0) continue;
          if (result === null || typeof result !== "object") throw new TypeError("Object expected");
          if (_ = accept(result.get)) descriptor.get = _;
          if (_ = accept(result.set)) descriptor.set = _;
          if (_ = accept(result.init)) initializers.unshift(_);
      }
      else if (_ = accept(result)) {
          if (kind === "field") initializers.unshift(_);
          else descriptor[key] = _;
      }
  }
  if (target) Object.defineProperty(target, contextIn.name, descriptor);
  done = true;
};

function __runInitializers(thisArg, initializers, value) {
  var useValue = arguments.length > 2;
  for (var i = 0; i < initializers.length; i++) {
      value = useValue ? initializers[i].call(thisArg, value) : initializers[i].call(thisArg);
  }
  return useValue ? value : void 0;
};

function __propKey(x) {
  return typeof x === "symbol" ? x : "".concat(x);
};

function __setFunctionName(f, name, prefix) {
  if (typeof name === "symbol") name = name.description ? "[".concat(name.description, "]") : "";
  return Object.defineProperty(f, "name", { configurable: true, value: prefix ? "".concat(prefix, " ", name) : name });
};

function __metadata(metadataKey, metadataValue) {
  if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(metadataKey, metadataValue);
}

function __awaiter(thisArg, _arguments, P, generator) {
  function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
  return new (P || (P = Promise))(function (resolve, reject) {
      function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
      function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
      function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
      step((generator = generator.apply(thisArg, _arguments || [])).next());
  });
}

function __generator(thisArg, body) {
  var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g = Object.create((typeof Iterator === "function" ? Iterator : Object).prototype);
  return g.next = verb(0), g["throw"] = verb(1), g["return"] = verb(2), typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
  function verb(n) { return function (v) { return step([n, v]); }; }
  function step(op) {
      if (f) throw new TypeError("Generator is already executing.");
      while (g && (g = 0, op[0] && (_ = 0)), _) try {
          if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
          if (y = 0, t) op = [op[0] & 2, t.value];
          switch (op[0]) {
              case 0: case 1: t = op; break;
              case 4: _.label++; return { value: op[1], done: false };
              case 5: _.label++; y = op[1]; op = [0]; continue;
              case 7: op = _.ops.pop(); _.trys.pop(); continue;
              default:
                  if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                  if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                  if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                  if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                  if (t[2]) _.ops.pop();
                  _.trys.pop(); continue;
          }
          op = body.call(thisArg, _);
      } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
      if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
  }
}

var __createBinding = Object.create ? (function(o, m, k, k2) {
  if (k2 === undefined) k2 = k;
  var desc = Object.getOwnPropertyDescriptor(m, k);
  if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
  }
  Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
  if (k2 === undefined) k2 = k;
  o[k2] = m[k];
});

function __exportStar(m, o) {
  for (var p in m) if (p !== "default" && !Object.prototype.hasOwnProperty.call(o, p)) __createBinding(o, m, p);
}

function __values(o) {
  var s = typeof Symbol === "function" && Symbol.iterator, m = s && o[s], i = 0;
  if (m) return m.call(o);
  if (o && typeof o.length === "number") return {
      next: function () {
          if (o && i >= o.length) o = void 0;
          return { value: o && o[i++], done: !o };
      }
  };
  throw new TypeError(s ? "Object is not iterable." : "Symbol.iterator is not defined.");
}

function __read(o, n) {
  var m = typeof Symbol === "function" && o[Symbol.iterator];
  if (!m) return o;
  var i = m.call(o), r, ar = [], e;
  try {
      while ((n === void 0 || n-- > 0) && !(r = i.next()).done) ar.push(r.value);
  }
  catch (error) { e = { error: error }; }
  finally {
      try {
          if (r && !r.done && (m = i["return"])) m.call(i);
      }
      finally { if (e) throw e.error; }
  }
  return ar;
}

/** @deprecated */
function __spread() {
  for (var ar = [], i = 0; i < arguments.length; i++)
      ar = ar.concat(__read(arguments[i]));
  return ar;
}

/** @deprecated */
function __spreadArrays() {
  for (var s = 0, i = 0, il = arguments.length; i < il; i++) s += arguments[i].length;
  for (var r = Array(s), k = 0, i = 0; i < il; i++)
      for (var a = arguments[i], j = 0, jl = a.length; j < jl; j++, k++)
          r[k] = a[j];
  return r;
}

function __spreadArray(to, from, pack) {
  if (pack || arguments.length === 2) for (var i = 0, l = from.length, ar; i < l; i++) {
      if (ar || !(i in from)) {
          if (!ar) ar = Array.prototype.slice.call(from, 0, i);
          ar[i] = from[i];
      }
  }
  return to.concat(ar || Array.prototype.slice.call(from));
}

function __await(v) {
  return this instanceof __await ? (this.v = v, this) : new __await(v);
}

function __asyncGenerator(thisArg, _arguments, generator) {
  if (!Symbol.asyncIterator) throw new TypeError("Symbol.asyncIterator is not defined.");
  var g = generator.apply(thisArg, _arguments || []), i, q = [];
  return i = Object.create((typeof AsyncIterator === "function" ? AsyncIterator : Object).prototype), verb("next"), verb("throw"), verb("return", awaitReturn), i[Symbol.asyncIterator] = function () { return this; }, i;
  function awaitReturn(f) { return function (v) { return Promise.resolve(v).then(f, reject); }; }
  function verb(n, f) { if (g[n]) { i[n] = function (v) { return new Promise(function (a, b) { q.push([n, v, a, b]) > 1 || resume(n, v); }); }; if (f) i[n] = f(i[n]); } }
  function resume(n, v) { try { step(g[n](v)); } catch (e) { settle(q[0][3], e); } }
  function step(r) { r.value instanceof __await ? Promise.resolve(r.value.v).then(fulfill, reject) : settle(q[0][2], r); }
  function fulfill(value) { resume("next", value); }
  function reject(value) { resume("throw", value); }
  function settle(f, v) { if (f(v), q.shift(), q.length) resume(q[0][0], q[0][1]); }
}

function __asyncDelegator(o) {
  var i, p;
  return i = {}, verb("next"), verb("throw", function (e) { throw e; }), verb("return"), i[Symbol.iterator] = function () { return this; }, i;
  function verb(n, f) { i[n] = o[n] ? function (v) { return (p = !p) ? { value: __await(o[n](v)), done: false } : f ? f(v) : v; } : f; }
}

function __asyncValues(o) {
  if (!Symbol.asyncIterator) throw new TypeError("Symbol.asyncIterator is not defined.");
  var m = o[Symbol.asyncIterator], i;
  return m ? m.call(o) : (o = typeof __values === "function" ? __values(o) : o[Symbol.iterator](), i = {}, verb("next"), verb("throw"), verb("return"), i[Symbol.asyncIterator] = function () { return this; }, i);
  function verb(n) { i[n] = o[n] && function (v) { return new Promise(function (resolve, reject) { v = o[n](v), settle(resolve, reject, v.done, v.value); }); }; }
  function settle(resolve, reject, d, v) { Promise.resolve(v).then(function(v) { resolve({ value: v, done: d }); }, reject); }
}

function __makeTemplateObject(cooked, raw) {
  if (Object.defineProperty) { Object.defineProperty(cooked, "raw", { value: raw }); } else { cooked.raw = raw; }
  return cooked;
};

var __setModuleDefault = Object.create ? (function(o, v) {
  Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
  o["default"] = v;
};

var ownKeys = function(o) {
  ownKeys = Object.getOwnPropertyNames || function (o) {
    var ar = [];
    for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
    return ar;
  };
  return ownKeys(o);
};

function __importStar(mod) {
  if (mod && mod.__esModule) return mod;
  var result = {};
  if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
  __setModuleDefault(result, mod);
  return result;
}

function __importDefault(mod) {
  return (mod && mod.__esModule) ? mod : { default: mod };
}

function __classPrivateFieldGet(receiver, state, kind, f) {
  if (kind === "a" && !f) throw new TypeError("Private accessor was defined without a getter");
  if (typeof state === "function" ? receiver !== state || !f : !state.has(receiver)) throw new TypeError("Cannot read private member from an object whose class did not declare it");
  return kind === "m" ? f : kind === "a" ? f.call(receiver) : f ? f.value : state.get(receiver);
}

function __classPrivateFieldSet(receiver, state, value, kind, f) {
  if (kind === "m") throw new TypeError("Private method is not writable");
  if (kind === "a" && !f) throw new TypeError("Private accessor was defined without a setter");
  if (typeof state === "function" ? receiver !== state || !f : !state.has(receiver)) throw new TypeError("Cannot write private member to an object whose class did not declare it");
  return (kind === "a" ? f.call(receiver, value) : f ? f.value = value : state.set(receiver, value)), value;
}

function __classPrivateFieldIn(state, receiver) {
  if (receiver === null || (typeof receiver !== "object" && typeof receiver !== "function")) throw new TypeError("Cannot use 'in' operator on non-object");
  return typeof state === "function" ? receiver === state : state.has(receiver);
}

function __addDisposableResource(env, value, async) {
  if (value !== null && value !== void 0) {
    if (typeof value !== "object" && typeof value !== "function") throw new TypeError("Object expected.");
    var dispose, inner;
    if (async) {
      if (!Symbol.asyncDispose) throw new TypeError("Symbol.asyncDispose is not defined.");
      dispose = value[Symbol.asyncDispose];
    }
    if (dispose === void 0) {
      if (!Symbol.dispose) throw new TypeError("Symbol.dispose is not defined.");
      dispose = value[Symbol.dispose];
      if (async) inner = dispose;
    }
    if (typeof dispose !== "function") throw new TypeError("Object not disposable.");
    if (inner) dispose = function() { try { inner.call(this); } catch (e) { return Promise.reject(e); } };
    env.stack.push({ value: value, dispose: dispose, async: async });
  }
  else if (async) {
    env.stack.push({ async: true });
  }
  return value;
}

var _SuppressedError = (/* unused pure expression or super */ null && (typeof SuppressedError === "function" ? SuppressedError : function (error, suppressed, message) {
  var e = new Error(message);
  return e.name = "SuppressedError", e.error = error, e.suppressed = suppressed, e;
}));

function __disposeResources(env) {
  function fail(e) {
    env.error = env.hasError ? new _SuppressedError(e, env.error, "An error was suppressed during disposal.") : e;
    env.hasError = true;
  }
  var r, s = 0;
  function next() {
    while (r = env.stack.pop()) {
      try {
        if (!r.async && s === 1) return s = 0, env.stack.push(r), Promise.resolve().then(next);
        if (r.dispose) {
          var result = r.dispose.call(r.value);
          if (r.async) return s |= 2, Promise.resolve(result).then(next, function(e) { fail(e); return next(); });
        }
        else s |= 1;
      }
      catch (e) {
        fail(e);
      }
    }
    if (s === 1) return env.hasError ? Promise.reject(env.error) : Promise.resolve();
    if (env.hasError) throw env.error;
  }
  return next();
}

function __rewriteRelativeImportExtension(path, preserveJsx, extraExtensions, ignoreCase) {
  if (typeof path === "string" && /^\.\.?\//.test(path)) {
      if (extraExtensions) {
          for (var extension in extraExtensions) {
              var suffix = path.slice(-extension.length);
              if (suffix === extension || ignoreCase && suffix.toLowerCase() === extension.toLowerCase()) {
                  var output = extraExtensions[extension];
                  return output === extension ? path : path.slice(0, -extension.length) + output;
              }
          }
      }
      return path.replace(/\.(tsx)$|((?:\.d)?)((?:\.[^./]+?)?)\.([cm]?)ts$/i, function (m, tsx, d, ext, cm) {
          return tsx ? preserveJsx ? ".jsx" : ".js" : d && (!ext || !cm) ? m : (d + ext + "." + cm.toLowerCase() + "js");
      });
  }
  return path;
}

/* unused harmony default export */ var __WEBPACK_DEFAULT_EXPORT__ = ((/* unused pure expression or super */ null && ({
  __extends,
  __assign,
  __rest,
  __decorate,
  __param,
  __esDecorate,
  __runInitializers,
  __propKey,
  __setFunctionName,
  __metadata,
  __awaiter,
  __generator,
  __createBinding,
  __exportStar,
  __values,
  __read,
  __spread,
  __spreadArrays,
  __spreadArray,
  __await,
  __asyncGenerator,
  __asyncDelegator,
  __asyncValues,
  __makeTemplateObject,
  __importStar,
  __importDefault,
  __classPrivateFieldGet,
  __classPrivateFieldSet,
  __classPrivateFieldIn,
  __addDisposableResource,
  __disposeResources,
  __rewriteRelativeImportExtension,
})));


/***/ }

/******/ 	});
/************************************************************************/
/******/ 	// The module cache
/******/ 	const __webpack_module_cache__ = {};
/******/ 	
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/ 		// Check if module is in cache
/******/ 		const cachedModule = __webpack_module_cache__[moduleId];
/******/ 		if (cachedModule !== undefined) {
/******/ 			return cachedModule.exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		const module = __webpack_module_cache__[moduleId] = {
/******/ 			// no module.id needed
/******/ 			// no module.loaded needed
/******/ 			exports: {}
/******/ 		};
/******/ 	
/******/ 		// Execute the module function
/******/ 		__webpack_modules__[moduleId](module, module.exports, __webpack_require__);
/******/ 	
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/ 	
/************************************************************************/
/******/ 	/* webpack/runtime/define property getters */
/******/ 	(() => {
/******/ 		// define getter/value functions for harmony exports
/******/ 		__webpack_require__.d = (exports, definition) => {
/******/ 			if(Array.isArray(definition)) {
/******/ 				var i = 0;
/******/ 				while(i < definition.length) {
/******/ 					var key = definition[i++];
/******/ 					var binding = definition[i++];
/******/ 					if(!__webpack_require__.o(exports, key)) {
/******/ 						if(binding === 0) {
/******/ 							Object.defineProperty(exports, key, { enumerable: true, value: definition[i++] });
/******/ 						} else {
/******/ 							Object.defineProperty(exports, key, { enumerable: true, get: binding });
/******/ 						}
/******/ 					} else if(binding === 0) { i++; }
/******/ 				}
/******/ 			} else {
/******/ 				for(var key in definition) {
/******/ 					if(__webpack_require__.o(definition, key) && !__webpack_require__.o(exports, key)) {
/******/ 						Object.defineProperty(exports, key, { enumerable: true, get: definition[key] });
/******/ 					}
/******/ 				}
/******/ 			}
/******/ 		};
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/hasOwnProperty shorthand */
/******/ 	(() => {
/******/ 		__webpack_require__.o = (obj, prop) => (Object.hasOwn(obj, prop))
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/make namespace object */
/******/ 	(() => {
/******/ 		// define __esModule on exports
/******/ 		__webpack_require__.r = (exports) => {
/******/ 			if(Symbol.toStringTag) {
/******/ 				Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });
/******/ 			}
/******/ 			Object.defineProperty(exports, '__esModule', { value: true });
/******/ 		};
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/wrap commonjs module */
/******/ 	(() => {
/******/ 		// execute a CommonJS module body with real module/exports objects, returning the final exports
/******/ 		__webpack_require__.cjs = (body) => {
/******/ 			const mod = { exports: {} };
/******/ 			body.call(mod.exports, mod, mod.exports);
/******/ 			return mod.exports;
/******/ 		};
/******/ 	})();
/******/ 	
/************************************************************************/
let __webpack_exports__ = {};
// This entry needs to be wrapped in an IIFE because it needs to be in strict mode.
(() => {
"use strict";
// ESM COMPAT FLAG
__webpack_require__.r(__webpack_exports__);

// EXPORTS
__webpack_require__.d(__webpack_exports__, {
  handler: () => (/* binding */ handler),
  mergeCheck: () => (/* binding */ mergeCheck)
});

;// ./node_modules/@forge/resolver/out/index.js
var out_namespaceObject = /*#__PURE__*/__webpack_require__.cjs(function(module, exports) {
var __webpack_unused_export__;

__webpack_unused_export__ = ({ value: true });
__webpack_unused_export__ = makeResolver;
class Resolver {
    functions;
    constructor() {
        this.functions = {};
    }
    define(functionKey, cb) {
        if (!cb || typeof cb !== 'function') {
            throw new Error(`Resolver definition '${functionKey}' callback must be a 'function'. Received '${typeof cb}'.`);
        }
        if (functionKey in this.functions) {
            throw new Error(`Resolver definition '${functionKey}' already exists.`);
        }
        // Individual resolver functions are not type-checked inside the array. The
        // types are only checked when adding them via makeResolver.
        this.functions[functionKey] = cb;
        return this;
    }
    getFunction(functionKey) {
        if (functionKey in this.functions) {
            return this.functions[functionKey];
        }
        throw new Error(`Resolver has no definition for '${functionKey}'.`);
    }
    sanitizeObject(object) {
        return JSON.parse(JSON.stringify(object));
    }
    getDefinitions() {
        return async ({ call: { functionKey, payload, jobId }, context }, backendRuntimePayload) => {
            const cb = this.getFunction(functionKey);
            const result = await cb({
                payload: payload || {},
                context: {
                    ...context,
                    installContext: backendRuntimePayload?.installContext,
                    accountId: backendRuntimePayload?.principal?.accountId,
                    license: backendRuntimePayload?.license,
                    jobId: jobId,
                    installation: backendRuntimePayload?.installation
                }
            });
            if (typeof result === 'object') {
                return this.sanitizeObject(result);
            }
            return result;
        };
    }
}
exports.Ay = Resolver;
/**
 * Creates resolver definitions corresponding to a given Definitions type.
 *
 * @param handlers Resolver functions implementing the definitions
 * @returns Resolver definitions
 */
function makeResolver(handlers) {
    const resolver = new Resolver();
    for (const key of Object.keys(handlers)) {
        resolver.define(key, handlers[key]);
    }
    return resolver.getDefinitions();
}

});

// EXTERNAL MODULE: ./node_modules/@forge/api/out/index.js
var out = __webpack_require__(7274);
;// ./src/specweft.js
// Core logic shared by the PR panel resolver and the merge check.
// Dependencies are injected so the logic is unit-testable without the Forge runtime:
//   deps.getRepo(workspaceId, repoUuid)        -> { slug, full_name, is_private }
//   deps.getDiff(workspaceId, repoUuid, prId)  -> unified diff text
//   deps.backend(path, body)                   -> parsed JSON from the SpecWeft backend (throws on non-2xx)

const MAX_DIFF_CHARS = 4500000; // backend accepts 5 MB; keep a margin

class UserError extends Error {}
async function buildRequest(workspaceId, repoUuid, prId, deps) {
  if (!workspaceId || !repoUuid || !prId) {
    throw new UserError('Missing pull request context (workspace, repository or PR id).');
  }
  const [repo, diff] = await Promise.all([deps.getRepo(workspaceId, repoUuid), deps.getDiff(workspaceId, repoUuid, prId)]);
  if (diff.length > MAX_DIFF_CHARS) {
    throw new UserError('This pull request diff is too large for SpecWeft to analyze.');
  }
  return {
    repo_slug: repo.slug,
    repo_full_name: repo.full_name,
    is_private: Boolean(repo.is_private),
    pr_id: Number(prId),
    diff
  };
}

/** PR panel: fetch repo + diff from Bitbucket, ask the backend for ranked, evidence-backed recommendations. */
async function analyzePullRequest({
  workspaceId,
  repoUuid,
  prId
}, deps) {
  const body = await buildRequest(workspaceId, repoUuid, prId, deps);
  return deps.backend('/forge/analyze-pr', body);
}

/** Merge check: returns Bitbucket's MergeCheckResponse { success, message }. Never fails because SpecWeft failed. */
async function runMergeCheck(event, deps) {
  try {
    var _event$workspace, _event$repository, _event$pullrequest;
    const body = await buildRequest(event === null || event === void 0 || (_event$workspace = event.workspace) === null || _event$workspace === void 0 ? void 0 : _event$workspace.uuid, event === null || event === void 0 || (_event$repository = event.repository) === null || _event$repository === void 0 ? void 0 : _event$repository.uuid, event === null || event === void 0 || (_event$pullrequest = event.pullrequest) === null || _event$pullrequest === void 0 ? void 0 : _event$pullrequest.id, deps);
    const res = await deps.backend('/forge/merge-check', body);
    return {
      success: Boolean(res.success),
      message: String(res.message ?? '')
    };
  } catch (e) {
    return {
      success: true,
      message: `SpecWeft check skipped: ${e.message}`
    };
  }
}
;// ./src/index.js



const REMOTE = 'specweft-backend';
async function ensureOk(res, what) {
  if (!res.ok) throw new UserError(`Bitbucket API returned ${res.status} for ${what}.`);
  return res;
}

// `route` URL-encodes interpolated values (Bitbucket UUIDs contain braces).
const deps = {
  async getRepo(ws, repo) {
    const res = await out/* default.asApp */.Ay.asApp().requestBitbucket((0,out/* route */.wE)`/2.0/repositories/${ws}/${repo}`);
    return (await ensureOk(res, 'repository')).json();
  },
  async getDiff(ws, repo, pr) {
    const res = await out/* default.asApp */.Ay.asApp().requestBitbucket((0,out/* route */.wE)`/2.0/repositories/${ws}/${repo}/pullrequests/${pr}/diff`);
    return (await ensureOk(res, 'pull request diff')).text();
  },
  async backend(path, body) {
    const res = await (0,out/* invokeRemote */.Tg)(REMOTE, {
      path,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    });
    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = {
        detail: text.slice(0, 300)
      };
    }
    if (!res.ok) {
      const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      throw new UserError(`SpecWeft backend returned ${res.status}: ${detail}`);
    }
    return data;
  }
};
const resolver = new out_namespaceObject.Ay();
resolver.define('analyze', async ({
  context
}) => {
  const ext = (context === null || context === void 0 ? void 0 : context.extension) ?? {};
  try {
    var _ext$repository, _ext$pullRequest;
    const result = await analyzePullRequest({
      workspaceId: context === null || context === void 0 ? void 0 : context.workspaceId,
      repoUuid: ext === null || ext === void 0 || (_ext$repository = ext.repository) === null || _ext$repository === void 0 ? void 0 : _ext$repository.uuid,
      prId: ext === null || ext === void 0 || (_ext$pullRequest = ext.pullRequest) === null || _ext$pullRequest === void 0 ? void 0 : _ext$pullRequest.id
    }, deps);
    return {
      ok: true,
      result
    };
  } catch (e) {
    console.error('specweft analyze failed', e);
    return {
      ok: false,
      error: e instanceof UserError ? e.message : 'Unexpected error while analyzing this pull request.'
    };
  }
});
const handler = resolver.getDefinitions();
const mergeCheck = async event => runMergeCheck(event, deps);
})();

const __webpack_export_target__ = exports;
for(var __webpack_i__ in __webpack_exports__) __webpack_export_target__[__webpack_i__] = __webpack_exports__[__webpack_i__];
if(__webpack_exports__.__esModule) Object.defineProperty(__webpack_export_target__, "__esModule", { value: true });
/******/ })()
;
//# sourceMappingURL=index.cjs.map