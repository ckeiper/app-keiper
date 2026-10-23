"""Navy theme scoped to the client directory and its CRM card."""
NAVY_HOME_CSS = """<style>
body:has(.kh-home){color-scheme:dark;background:radial-gradient(ellipse at 15% 0%,#142c50 0%,transparent 45%),#0b1426;color:#e9f0ff;min-height:100vh}
body:has(.kh-home) .top{background:#0d192dcc;border-bottom:1px solid #273953;box-shadow:none}
body:has(.kh-home) .top h1{color:#eff5ff}body:has(.kh-home) .top .brand{color:#9db1ce}
body:has(.kh-home) .top a.btn{background:#244a80;border-color:#365c91;color:#eaf2ff;box-shadow:none}
body:has(.kh-home) .top a.btn:hover{background:#315e9a}
body:has(.kh-home) .kh-home{color:#e9f0ff}
body:has(.kh-home) .kh-head{border-color:#293b56}
body:has(.kh-home) .kh-home h2{color:#f2f6ff;display:flex;align-items:center;gap:15px;flex-wrap:wrap}
body:has(.kh-home) .kh-eyebrow{color:#86adf0}
body:has(.kh-home) .kh-count{background:#1a2b45;border-color:#334968;color:#a8bfdf;letter-spacing:0}
body:has(.kh-home) .kh-store{background:linear-gradient(125deg,#192b45,#14233a);border-color:#2d425e;box-shadow:0 8px 24px #00000014}
body:has(.kh-home) .kh-store:hover,body:has(.kh-home) .kh-store:focus-within{background:linear-gradient(125deg,#203858,#192d49);border-color:#557eb7;box-shadow:0 12px 28px #00000030}
body:has(.kh-home) .kh-store:before{background:#6b9cf0}
body:has(.kh-home) .kh-store-name{color:#edf3ff}
body:has(.kh-home) .kh-store-icon{background:linear-gradient(140deg,#24436d,#203859);color:#92bcff;box-shadow:inset 0 1px 0 #ffffff08}
body:has(.kh-home) .kh-status,body:has(.kh-home) .kh-active{color:#9cb3d1}
body:has(.kh-home) .kh-inactive{color:#e6b880}
body:has(.kh-home) .kh-trend.up{color:#59d8aa}body:has(.kh-home) .kh-trend.down{color:#ff8897}body:has(.kh-home) .kh-trend.flat{color:#a4b6cf}
body:has(.kh-home) .kh-more{color:#a1b8d8}
body:has(.kh-home) .kh-more:hover,body:has(.kh-home) .kh-more[aria-expanded=true]{background:#2b4364;color:#e6efff}
body:has(.kh-home) .kh-menu{background:#1b2c46;border-color:#3b5476;box-shadow:0 18px 40px #00000055}
body:has(.kh-home) .kh-menu button,body:has(.kh-home) .kh-menu a{color:#e0eaff}
body:has(.kh-home) .kh-menu button:hover,body:has(.kh-home) .kh-menu a:hover{background:#2c4568}
body:has(.kh-home) .kh-menu .kh-danger{color:#ffa1ab}
body:has(.kh-home) .kh-empty{background:#15253d;border-color:#344e70;color:#a6bbd7}
body:has(.kh-home) .kc-wrap{color:#dfebff}
body:has(.kh-home) .kc-panel{background:linear-gradient(125deg,#1a2d49,#14243b 55%,#172a43);border-color:#304766;box-shadow:0 12px 36px #00000022}
body:has(.kh-home) .kc-panel:before{background:linear-gradient(90deg,#5b92ed,#899de9 55%,#65c8bd)}
body:has(.kh-home) .kc-emblem{background:#29446b;color:#a4c5ff;box-shadow:inset 0 1px 0 #ffffff0c}
body:has(.kh-home) .kc-eyebrow{color:#94b5ed}
body:has(.kh-home) .kc-panel h3{color:#f1f5ff}body:has(.kh-home) .kc-panel p{color:#a4b7d2}
body:has(.kh-home) .kc-button{background:#213957;border-color:#3c567a;color:#c9ddff}
body:has(.kh-home) .kc-button:hover{background:#2b486c}
body:has(.kh-home) .kc-button.kc-primary{background:#447cdb;color:#fff;border-color:#5b93ee;box-shadow:0 6px 16px #00000022}
body:has(.kh-home) .kc-button.kc-primary:hover{background:#558eea}
body:has(.kh-home) .kc-stat{background:#112139a6;border-color:#334966}
body:has(.kh-home) .kc-stat:hover{background:#203b5c;border-color:#6082b1}
body:has(.kh-home) .kc-stat strong{color:#d7e5ff}body:has(.kh-home) .kc-stat span{color:#acbfda}
body:has(.kh-home) .kc-stat i{background:#263b58;color:#a9bddb}
body:has(.kh-home) .kc-stat.kc-overdue strong{color:#ffa1a1}body:has(.kh-home) .kc-stat.kc-overdue i{background:#50353f;color:#ffadac}
body:has(.kh-home) .kc-stat.kc-today strong{color:#99beff}body:has(.kh-home) .kc-stat.kc-today i{background:#27446e;color:#a6c7ff}
body:has(.kh-home) .kc-agenda{border-color:#334864}
body:has(.kh-home) .kc-agenda h4{color:#c1d3ec}body:has(.kh-home) .kc-agenda-title>span{color:#9db2d0}
body:has(.kh-home) .kc-lead{border-color:#2a405c;color:#e4edff}
body:has(.kh-home) .kc-lead:hover{background:#263d5b}
body:has(.kh-home) .kc-avatar{background:#2a4265;color:#b6cefa}
body:has(.kh-home) .kc-lead-next{color:#acbed8}
body:has(.kh-home) .kc-date{background:#29496f;color:#b1d0ff}
body:has(.kh-home) .kc-date.kc-late{background:#50373f;color:#ffb0ac}
body:has(.kh-home) .kc-lead>svg{color:#a1b9d9}
body:has(.kh-home) .kc-empty>svg{color:#73d6bd}body:has(.kh-home) .kc-empty strong{color:#c6d7ed}
body:has(.kh-home) .kc-loading{color:#a7bddb}
body:has(.kh-home) .kc-foot{background:#112036;border-color:#314662}
body:has(.kh-home) .kc-foot strong{color:#bfd2ef}body:has(.kh-home) .kc-foot-copy>svg{color:#a1bce3}
body:has(.kh-home) .kc-foot .kc-button{background:#203751}
body:has(.kh-home) .kh-health{background:linear-gradient(125deg,#192b45,#14233a);border-color:#2d425e;color:#edf3ff;box-shadow:0 8px 24px #00000014}
body:has(.kh-home) .kh-health-head h3{color:#f2f6ff}
body:has(.kh-home) .kh-health-head p,body:has(.kh-home) .kh-health-foot{color:#a4b6d0}
body:has(.kh-home) .kh-health-eyebrow,body:has(.kh-home) .kh-health-head a{color:#94b5ed}
body:has(.kh-home) .kh-health-item{background:#112139;border-color:#3b4e69;color:#edf3ff}
body:has(.kh-home) .kh-health-item:hover{background:#203858;border-color:#557eb7}
body:has(.kh-home) .kh-health-item span{color:#ffb0ac}
body:has(.kh-home) .kh-health-item small{color:#aac8f6}
body:has(.kh-home) .kh-health-empty{color:#72dfb5}
</style>"""
