// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.provide("frappe_investments.integrations");

frappe.ui.form.on("Investment Plaid Settings", {
	enabled: function (frm) {
		frm.toggle_reqd("plaid_client_id", frm.doc.enabled);
		frm.toggle_reqd("plaid_secret", frm.doc.enabled);
		frm.toggle_reqd("plaid_env", frm.doc.enabled);
	},

	refresh: function (frm) {
		if (frm.doc.enabled) {
			frm.add_custom_button(__("Link a new investment institution"), () => {
				new frappe_investments.integrations.investmentPlaidLink(frm);
			});

			frm.add_custom_button(__("Reset Plaid Link"), () => {
				new frappe_investments.integrations.investmentPlaidLink(frm);
			});

			frm.add_custom_button(__("Sync Now"), () => {
				frappe.call({
					method: "frappe_investments.investments.doctype.investment_plaid_settings.investment_plaid_settings.enqueue_investment_synchronization",
					freeze: true,
					callback: () => {
						let investment_account_link = frappe.utils.get_form_link(
							"Investment Account",
							"",
							true,
							__("Investment Account")
						);

						frappe.msgprint({
							title: __("Sync Started"),
							message: __(
								"The investment sync has started in the background, please check the {0} list for updated values.",
								[investment_account_link]
							),
							alert: 1,
						});
					},
				});
			}).addClass("btn-primary");
		}
	},
});

frappe_investments.integrations.investmentPlaidLink = class investmentPlaidLink {
	constructor(parent) {
		this.frm = parent;
		this.plaidUrl = "https://cdn.plaid.com/link/v2/stable/link-initialize.js";
		this.init_config();
	}

	async init_config() {
		this.product = ["investments"];
		this.plaid_env = this.frm.doc.plaid_env;
		this.client_name = frappe.boot.sitename;
		this.token = await this.get_link_token();
		this.init_plaid();
	}

	async get_link_token() {
		const token = await this.frm.call("get_link_token").then((resp) => resp.message);
		if (!token) {
			frappe.throw(__("Cannot retrieve link token. Check Error Log for more information"));
		}
		return token;
	}

	init_plaid() {
		const me = this;
		me.loadScript(me.plaidUrl)
			.then(() => {
				me.onScriptLoaded(me);
			})
			.then(() => {
				if (me.linkHandler) {
					me.linkHandler.open();
				}
			})
			.catch((error) => {
				me.onScriptError(error);
			});
	}

	loadScript(src) {
		return new Promise(function (resolve, reject) {
			if (document.querySelector('script[src="' + src + '"]')) {
				resolve();
				return;
			}
			const el = document.createElement("script");
			el.type = "text/javascript";
			el.async = true;
			el.src = src;
			el.addEventListener("load", resolve);
			el.addEventListener("error", reject);
			el.addEventListener("abort", reject);
			document.head.appendChild(el);
		});
	}

	onScriptLoaded(me) {
		me.linkHandler = Plaid.create({
			// eslint-disable-line no-undef
			clientName: me.client_name,
			product: me.product,
			env: me.plaid_env,
			token: me.token,
			onSuccess: me.plaid_success,
		});
	}

	onScriptError(error) {
		frappe.msgprint(
			__(
				"There was an issue connecting to Plaid's authentication server. Check browser console for more information"
			)
		);
		console.log(error);
	}

	plaid_success(token, response) {
		const me = this;

		frappe.prompt(
			{
				fieldtype: "Link",
				options: "Company",
				label: __("Company"),
				fieldname: "company",
				reqd: 1,
			},
			(data) => {
				me.company = data.company;
				frappe
					.xcall(
						"frappe_investments.investments.doctype.investment_plaid_settings.investment_plaid_settings.add_investment_institution",
						{
							token: token,
							response: response,
						}
					)
					.then((result) => {
						frappe.xcall(
							"frappe_investments.investments.doctype.investment_plaid_settings.investment_plaid_settings.add_investment_accounts",
							{
								response: response,
								institution: result,
								company: me.company,
							}
						);
					})
					.then(() => {
						frappe.show_alert({ message: __("Investment accounts added"), indicator: "green" });
					});
			},
			__("Select a company"),
			__("Continue")
		);
	}
};
